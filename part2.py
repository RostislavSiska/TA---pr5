
import re
import sys
from dataclasses import dataclass
from datetime import date


class ParseError(Exception):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: str


# Два формата дат:
# YYYY-MM-DD и DD.MM.YYYY
DATE_RE = re.compile(
    r'(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|'
    r'[0-9]{2}[.][0-9]{2}[.][0-9]{4})'
    r'(?![A-Za-z0-9_])'
)

# Идентификатор длиной 1-2 символа
IDENT_RE = re.compile(
    r'[A-Za-z][A-Za-z0-9]?(?![A-Za-z0-9_])'
)

# Целое десятичное число
INT_RE = re.compile(r'[0-9]+')

# Односимвольные операторы и скобки
SINGLE = {
    '+': 'PLUS',
    '-': 'MINUS',
    '!': 'BANG',
    '*': 'STAR',
    '/': 'SLASH',
    '=': 'EQ',
    '(': 'LPAREN',
    ')': 'RPAREN'
}


# ЛЕКСИЧЕСКИЙ АНАЛИЗАТОР
def tokenize(source: str):
    result = []
    i = 0
    n = len(source)

    while i < n:
        ch = source[i]

        # Пропуск пробелов и табуляции
        if ch in ' \t\f\v':
            i += 1
            continue

        # Разделители: новая строка и ;
        # Последовательные разделители объединяются
        if ch in '\r\n;':
            j = i

            while j < n:
                if source[j] in ' \t\f\v':
                    j += 1
                elif source[j] in '\r\n;':
                    if source.startswith('\r\n', j):
                        j += 2
                    else:
                        j += 1
                else:
                    break

            result.append(Token('SEP', source[i:j]))
            i = j
            continue

        # Проверка даты
        m = DATE_RE.match(source, i)

        if m:
            raw = m.group(0)

            try:
                if '-' in raw:
                    year, month, day = map(int, raw.split('-'))
                else:
                    day, month, year = map(int, raw.split('.'))

                # Проверка календарной корректности даты
                date(year, month, day)

            except ValueError as exc:
                raise ParseError('Некорректная дата') from exc

            result.append(Token('DATE', raw))
            i = m.end()
            continue

        # Проверка имени переменной
        m = IDENT_RE.match(source, i)

        if m:
            result.append(Token('ID', m.group(0)))
            i = m.end()
            continue

        # Проверка целочисленной константы
        m = INT_RE.match(source, i)

        if m:
            result.append(Token('INT', m.group(0)))
            i = m.end()
            continue

        # Проверка операторов и скобок
        if ch in SINGLE:
            result.append(Token(SINGLE[ch], ch))
            i += 1
            continue

        raise ParseError(f'Недопустимый символ: {ch!r}')

    result.append(Token('EOF', ''))
    return result


# СИНТАКСИЧЕСКИЙ АНАЛИЗАТОР
class Parser:

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    @property
    def current(self):
        return self.tokens[self.pos]

    def accept(self, kind):
        if self.current.kind == kind:
            self.pos += 1
            return True
        return False

    def expect(self, kind):
        if not self.accept(kind):
            raise ParseError(
                f'Ожидался {kind}, получен {self.current.kind}'
            )

    # S -> E R
    # R -> SEP H | epsilon
    # H -> E R | epsilon
    def parse_program(self):

        if self.current.kind in ('EOF', 'SEP'):
            raise ParseError('Ожидалось выражение')

        self.parse_expr()

        while self.accept('SEP'):
            if self.current.kind == 'EOF':
                break

            self.parse_expr()

        self.expect('EOF')

    # E -> ID X | V T A
    # X -> EQ E | T A
    def parse_expr(self):

        if self.accept('ID'):

            # Присваивание имеет наименьший приоритет.
            # Рекурсивный вызов обеспечивает
            # правоассоциативность присваивания.
            if self.accept('EQ'):
                self.parse_expr()

            else:
                self.parse_mul_tail()
                self.parse_add_tail()

        else:
            self.parse_non_id_start()
            self.parse_mul_tail()
            self.parse_add_tail()

    # V -> U W | INT | DATE | LPAREN E RPAREN
    def parse_non_id_start(self):

        if self.current.kind in (
            'PLUS', 'MINUS', 'BANG'
        ):
            self.parse_unary()

        elif self.accept('INT') or self.accept('DATE'):
            pass

        elif self.accept('LPAREN'):
            self.parse_expr()
            self.expect('RPAREN')

        else:
            raise ParseError('Недопустимое начало выражения')

    # W -> U W | P
    # Унарные операции
    def parse_unary(self):

        if self.current.kind in (
            'PLUS', 'MINUS', 'BANG'
        ):
            self.pos += 1
            self.parse_unary()

        else:
            self.parse_primary()

    # P -> ID | INT | DATE | LPAREN E RPAREN
    def parse_primary(self):

        if self.current.kind in ('ID', 'INT', 'DATE'):
            self.pos += 1

        elif self.accept('LPAREN'):
            self.parse_expr()
            self.expect('RPAREN')

        else:
            raise ParseError('Ожидался операнд')

    # T -> STAR W T | SLASH W T | epsilon
    # Умножение и деление
    def parse_mul_tail(self):

        while self.current.kind in ('STAR', 'SLASH'):
            self.pos += 1
            self.parse_unary()

    # M -> W T
    def parse_mul(self):

        self.parse_unary()
        self.parse_mul_tail()

    # A -> PLUS M A | MINUS M A | epsilon
    # Сложение и вычитание
    def parse_add_tail(self):

        while self.current.kind in ('PLUS', 'MINUS'):
            self.pos += 1
            self.parse_mul()


# ФУНКЦИЯ РАСПОЗНАВАНИЯ
def recognize(source: str) -> bool:

    try:
        tokens = tokenize(source)
        parser = Parser(tokens)
        parser.parse_program()
        return True

    except ParseError:
        return False


# ГЛАВНАЯ ФУНКЦИЯ
if __name__ == '__main__':

    print("Введите последовательность выражений.")
    print("Для завершения ввода напишите END:")

    lines = []

    try:
        while True:
            line = input()

            if line.strip() == "END":
                break

            lines.append(line)

    except EOFError:
        pass

    source = "\n".join(lines)

    if recognize(source):
        print("Accepted")
    else:
        print("Rejected")