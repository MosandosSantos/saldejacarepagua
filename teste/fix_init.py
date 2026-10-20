with open('/app/contatos/views/__init__.py') as f:
    lines = f.readlines()

# Find the line with 'membro_excluir', and insert 'membro_lista', after it
for i, line in enumerate(lines):
    if "'membro_excluir'," in line:
        lines.insert(i + 1, "    'membro_lista',\n")
        break

with open('/app/contatos/views/__init__.py', 'w') as f:
    f.writelines(lines)

print('Done')