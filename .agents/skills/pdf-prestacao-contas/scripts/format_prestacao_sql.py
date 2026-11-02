"""Formatação legível do SQL gerado, preservando strings e expressões."""
import re


def split_top(text, separator=','):
    parts, start, depth, quoted = [], 0, 0, False
    i = 0
    while i < len(text):
        char = text[i]
        if char == "'":
            if quoted and i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
            quoted = not quoted
        elif not quoted:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif depth == 0 and text.startswith(separator, i):
                parts.append(text[start:i].strip())
                i += len(separator)
                start = i
                continue
        i += 1
    return parts + [text[start:].strip()]


def section(title):
    rule = '-- ' + '=' * 76
    return f'{rule}\n-- {title}\n{rule}'


def format_sql(lines):
    output = []
    last_group = None
    batch_key = None
    batch_rows = []

    def flush():
        nonlocal batch_key, batch_rows
        if batch_key:
            table, fields = batch_key
            output.append(f"INSERT INTO {table} ({', '.join(fields)})\nVALUES\n" + ',\n'.join('    (' + ', '.join(row) + ')' for row in batch_rows) + ';')
        batch_key, batch_rows = None, []

    for line in lines:
        if line.startswith('INSERT INTO '):
            match = re.fullmatch(r'INSERT INTO (\w+) \((.*?)\) VALUES \((.*)\);', line)
            table, columns, raw_values = match.groups()
            fields = tuple(split_top(columns))
            values = split_top(raw_values)
            if table == 'meses':
                group = '2. Cadastro do mês e situação dos documentos'
            elif table in ('categorias', 'subcategorias'):
                group = '3. Estrutura de receitas' if values[1] == "'R'" else '4. Estrutura de despesas'
            elif 'ajuste de saldo' in values[3]:
                group = '7. Ajustes avulsos extra relatório — exclusivos de julho/2024'
            else:
                group = '5. Lançamentos de receitas' if values[1] == "'R'" else '6. Lançamentos de despesas'
            if group != last_group:
                flush()
                output.append(section(group))
                last_group = group
            key = (table, fields)
            if batch_key != key:
                flush()
                batch_key = key
            for i, field in enumerate(fields):
                if field in ('valor', 'receita_total', 'despesa_total'):
                    values[i] = f'{float(values[i]):.2f}'
            # Normalize operators only outside quoted SQL literals.
            values = [''.join(part if i % 2 else re.sub(r'\s*=\s*', ' = ', part)
                              for i, part in enumerate(re.split(r"('(?:''|[^'])*')", value)))
                      for value in values]
            batch_rows.append(values)
        else:
            flush()
            if line.startswith('DELETE FROM '):
                output.append(section('1. Limpeza da competência para reexecução'))
                output.append(re.sub(r'\s+WHERE\s+', '\nWHERE ', line, count=1))
            elif line == 'COMMIT;':
                output.extend([section('8. Conclusão da transação'), line])
            elif line.startswith('-- Lançamentos avulsos'):
                continue
            elif line.startswith('--') and output and output[-1].startswith('--') and last_group is None:
                output[-1] += '\n' + line
            else:
                output.append(line)
    flush()
    return '\n\n'.join(output) + '\n'
