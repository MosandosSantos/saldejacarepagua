# Spec: Exportação da Pirâmide de Graus

## Objetivo

Fornecer uma especificação portátil para implementar, em outra aplicação, a Pirâmide de Graus exibida no dashboard do Sal da Britânia CRM. O documento registra a regra de contagem, o escopo por tenant, a ordem e os limites das faixas, o contrato de dados, o desenho 3D e critérios verificáveis.

A aplicação de destino não foi definida. Portanto, esta especificação é neutra quanto a linguagem, framework, banco de dados e biblioteca gráfica; quem a implementar deverá adaptá-la às convenções do projeto de destino sem alterar as regras de negócio aqui descritas.

## História de usuário

### US1 (P1): Consultar a distribuição de graus

Como usuário autorizado do dashboard, quero ver Membros ativos agrupados pelo maior grau registrado, para entender a distribuição de graus no meu tenant permitido.

**Aceite:** cada Membro elegível aparece uma vez na faixa correta; histórico sem grau, tenant diferente e situação inativa não entram; as cinco faixas, contagens, percentuais, total e legenda SC33 são exibidos inclusive quando não há dados.

## Referência da implementação atual

- Agregação e escopo local: `dashboard/repositories/local_repository.py`, método `membros_ativos_por_faixa_de_graus()`.
- Montagem do contexto e do SVG: `dashboard/views.py`, funções `_buscar_dados_baii()`, `_para_svg_pyramide()` e `_pyramide_svg()`.
- Card do dashboard: `dashboard/templates/dashboard/index.html` e `dashboard/templates/dashboard/partials/_baii.html`.
- Regressões de domínio e renderização: `teste/test_dashboard_graus.py`.

O módulo fonte usa o nome **SCREAA** na faixa do grau 33. Por decisão do usuário, a aplicação de destino deve exibir **SC33**, para alinhar o rótulo à classificação dos Corpos. Essa padronização é de apresentação: o intervalo continua sendo somente o grau 33.

## Dados de entrada

O cálculo precisa de entidades equivalentes a:

| Entidade | Campos necessários | Uso |
|---|---|---|
| Membro | identificador, tenant, situação | Identificar membros ativos e evitar duplicidade. |
| Histórico de grau | membro, tenant, grau | Encontrar o maior grau registrado para cada membro, sem misturar tenants. |
| Grau | número inteiro | Classificar o maior grau em uma faixa. |

O catálogo válido de graus é **4º a 33º**, inclusive. A implementação atual mantém uma linha de histórico por membro/grau e limita o catálogo a essa faixa.

## Escopo e regras de negócio

1. Considerar apenas Membros com situação `ATIVO`.
2. Restringir Membros ao tenant efetivo do usuário. Uma sessão sem tenant selecionado, usada pelo `admin_saas` no sistema fonte, pode consultar todos os tenants autorizados.
3. Usar somente históricos cujo tenant seja o mesmo do Membro.
4. Para cada Membro elegível, calcular o maior número de grau registrado e classificá-lo em exatamente uma faixa. Não contar uma pessoa uma vez por linha de histórico.
5. Excluir Membros sem qualquer grau válido registrado. Eles não fazem parte do total da pirâmide.
6. Não filtrar pela potência, pelo Rito, pela Loja vinculada ou pelo Corpo da Loja. A classificação depende do maior grau do histórico, não de `Loja.corpo`.
7. Sempre retornar as cinco faixas na ordem da tabela abaixo, inclusive as faixas com zero Membros.
8. O total é a soma das contagens das cinco faixas; não é a contagem de todos os Membros ativos.

### Faixas

| Ordem visual | Graus | Rótulo no destino | Cor-base |
|---:|---:|---|---|
| Base | 4–14 | Perfeição | `#1a5fb4` |
| 2 | 15–18 | Capítulo | `#1a5fb4` |
| 3 | 19–30 | Kadosh | `#3b7ded` |
| 4 | 31–32 | Consistório | `#93b8f7` |
| Topo | 33 | SC33 | `#93b8f7` |

### Pseudocódigo de referência

```text
faixas = criar cinco contadores zerados, na ordem especificada

para cada membro ATIVO do escopo de tenant autorizado:
    graus = históricos do membro cujo tenant coincide com o tenant do membro
    se graus estiver vazio:
        continuar

    maior_grau = máximo(graus.numero)
    faixa = única faixa que contém maior_grau
    faixa.total += 1

total = soma(faixa.total para cada faixa)
para cada faixa:
    faixa.percentual = arredondar(faixa.total / total * 100) se total > 0; caso contrário 0
```

Na implementação fonte, as datas de obtenção não alteram a classificação: usa-se somente o número mais alto de grau no histórico. O percentual é calculado com `round(count / total * 100)`; o `round` de Python usa arredondamento de empate para o par. Se o destino usar outra linguagem, deve reproduzir esse comportamento para manter paridade nos casos de empate.

## Contrato de saída

O adaptador da aplicação de destino deve fornecer à interface uma estrutura equivalente a:

```json
{
  "total": 8,
  "faixas": [
    {"minimo": 4, "maximo": 14, "nome": "4–14", "rotulo": "Perfeição", "total": 1, "percentual": 13, "cor": "#1a5fb4"},
    {"minimo": 15, "maximo": 18, "nome": "15–18", "rotulo": "Capítulo", "total": 2, "percentual": 25, "cor": "#1a5fb4"},
    {"minimo": 19, "maximo": 30, "nome": "19–30", "rotulo": "Kadosh", "total": 2, "percentual": 25, "cor": "#3b7ded"},
    {"minimo": 31, "maximo": 32, "nome": "31–32", "rotulo": "Consistório", "total": 2, "percentual": 25, "cor": "#93b8f7"},
    {"minimo": 33, "maximo": 33, "nome": "33", "rotulo": "SC33", "total": 1, "percentual": 13, "cor": "#93b8f7"}
  ]
}
```

Os números do exemplo são ilustrativos. Em produção, `total` e cada contagem devem vir da agregação. Percentuais são arredondados individualmente; por isso, a soma exibida pode diferir de 100% por arredondamento. Com `total = 0`, todas as contagens e percentuais são zero e as cinco faixas continuam presentes.

## Contrato visual

- Exibir um card intitulado **Pirâmide de Graus**, com subtítulo informando que os membros são agrupados pelo maior grau registrado e com o total calculado.
- Mostrar a pirâmide 3D e, ao lado, uma legenda com marcador de cor, intervalo, rótulo, contagem e percentual de cada faixa. Exibir também o total da legenda.
- A ordem lógica recebida é base → topo. O SVG fonte inverte essa lista para desenhar primeiro o ápice e terminar na base.
- A largura das fatias representa a posição na pirâmide, **não** a quantidade de Membros. Não usar largura ou área como escala quantitativa.
- A fatia contém o rótulo e a contagem. O percentual aparece na legenda lateral.
- Reproduzir o tratamento 3D: face frontal em gradiente, face lateral escurecida, traço horizontal entre fatias, elipse de sombra e elipse inferior da base.
- Valores textuais interpolados em SVG devem ser escapados; não concatenar rótulos não confiáveis sem escape.
- A legenda textual deve continuar disponível como alternativa legível ao SVG.

### Geometria de referência do SVG fonte

Os valores abaixo dão paridade visual aproximada; podem ser adaptados a uma biblioteca gráfica do destino, mantendo a regra de que a largura representa a posição:

- `viewBox` base: largura 340; cada fatia tem altura 62 e intervalo vertical 5.
- Deslocamento de profundidade: `depthX = 22`, `depthY = 14`; topo em `y = 16`.
- Largura máxima da meia-base: `340 / 2 * 0.92`.
- Meia-largura cresce linearmente da fração mínima `0.18` até `1.0` conforme a posição vertical da faixa.
- Paleta fonte: `#1a5fb4`, `#3b7ded`, `#93b8f7`. A distribuição por base → topo é `#1a5fb4`, `#1a5fb4`, `#3b7ded`, `#93b8f7`, `#93b8f7`; usar essa sequência explícita para evitar diferenças de arredondamento entre linguagens.

## Estados vazios e falhas

- Sem Membros elegíveis ou sem histórico: retornar total zero e cinco faixas zeradas; renderizar estado vazio sem inventar totais.
- Falha ao consultar o repositório: registrar o erro e apresentar estado vazio seguro. Não substituir falha por dados de outro tenant.
- Grau fora do catálogo 4–33: rejeitar ou corrigir na camada de domínio/dados; não permitir que uma faixa desconhecida suma silenciosamente.
- Requisição sem tenant: aplicar a política de autorização da aplicação destino; não tratar ausência de contexto como autorização universal por padrão.

## Tecnologia, estrutura e comandos

- **Stack do destino:** não especificada; a implementação deve usar a camada de acesso a dados, a camada de apresentação e o framework de testes existentes.
- **Estrutura lógica recomendada:** serviço/repositório de agregação; componente visual da pirâmide; legenda textual acessível; testes unitários e de integração.
- **Comando de referência no sistema fonte:** com `VALE_TEST_DATABASE_URL` apontando para o PostgreSQL local de testes, executar `python -m pytest teste/test_dashboard_graus.py --ds=core.settings_vale_test -q`. O destino deve registrar seus próprios comandos de teste/build conforme o stack escolhido.

## Estratégia de testes

Cobrir comportamento real da agregação e da interface, sem depender apenas de testes de texto-fonte:

- maior grau prevalece quando há vários graus para o mesmo Membro;
- um Membro é contado uma única vez e somente em uma faixa;
- inativos, Membros sem grau e graus de tenant diferente não entram;
- tenant selecionado não vaza dados de outro tenant;
- graus de fronteira 14/15, 18/19, 30/31, 32/33 classificam corretamente;
- bandas vazias permanecem na resposta;
- total zero produz cinco faixas com contagem e percentual zero;
- percentuais e contagem do total refletem os mesmos Membros;
- SVG/legenda exibem rótulos, contagens e cores sem quebrar com caracteres especiais ou texto escapável.

## Limites

- **Sempre:** classificar pelo maior grau registrado; manter tenant e situação no escopo; contar cada Membro uma vez; manter a ordem e as cinco faixas; exibir SC33 no destino.
- **Não fazer:** classificar pela Loja, Corpo, potência ou Rito; incluir Membros sem histórico; dimensionar fatias pela quantidade; deduzir pagamentos de anuidade a partir da pirâmide; colapsar faixas vazias.
- **Perguntar antes:** alterar os limites das faixas, incluir outras categorias, mudar o significado do total, ou transformar o gráfico em funil/área proporcional à contagem.

## Critérios de sucesso

1. O destino apresenta exatamente cinco faixas, na ordem e com os limites especificados.
2. Cada Membro ativo com histórico do tenant autorizado aparece uma única vez, na faixa do seu maior grau.
3. Membros inativos, sem histórico ou com histórico de outro tenant não são contados.
4. As faixas vazias são exibidas com zero; `total` corresponde à soma das contagens.
5. A legenda exibe contagem e percentual; o SVG comunica a hierarquia sem sugerir que a largura representa quantidade.
6. O grau 33 é rotulado **SC33** na aplicação destino.

## Questões fora do escopo deste handoff

- Framework, linguagem, banco, autenticação e caminhos de arquivo do novo app.
- Filtros interativos por Rito, potência, Corpo ou Loja.
- Regras de cobrança/anuidade e a composição de outros cards do dashboard.
