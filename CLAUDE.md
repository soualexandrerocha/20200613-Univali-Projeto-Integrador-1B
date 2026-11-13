# Regras para sessões neste repositório

Várias sessões (pessoas e agentes) trabalham aqui ao mesmo tempo, e um
workflow agendado commita na `master` a cada 6 h. Para não gerar conflitos:

## Antes de começar
- Atualize e parta da `master`: `git fetch origin master` e crie ou
  recrie a branch a partir de `origin/master`.
- Se a branch da sessão já teve um PR mergeado, recomece-a da `master`
  atualizada em vez de empilhar commits sobre o histórico antigo.

## Arquivos que só o workflow commita
O workflow `.github/workflows/coleta-niveis.yml` é o único que commita:
- `dados/niveis/*.csv`: leituras de nível coletadas (um arquivo por coleta,
  nunca editado depois);
- `pagina/berco2.html`: painel gerado por `ferramentas/gerar_painel_berco2.py`.

Numa branch, não commite esses arquivos, mesmo que você os tenha gerado ou
coletado localmente para testar: descarte com
`git checkout -- pagina/berco2.html` e apague os CSV novos em `dados/niveis/`.
Mudou o modelo do painel (`pagina/modelo_berco2.html`) ou o gerador? Commite
só eles; o workflow regenera a página depois do merge. Para conferir a página
localmente, gere-a, teste e descarte.

## Tamanho e duração das mudanças
- Um tema por sessão e por PR; PRs pequenos, com merge logo.
- Antes de abrir o PR, confira se ele entra sem conflito:
  `git fetch origin master && git merge-tree --write-tree origin/master HEAD`.
- Se houver conflito, faça merge da `master` na branch (sem rebase nem
  force-push em branch de outra pessoa).

## Onde estão as coisas
- `mare_itajai.py`: maré astronômica (tábuas CHM 2024–2026).
- `cisalhamento_berco2_zp21.py`: corrente e tensão no Berço 2 (duas camadas).
- `analise_propagacao_mare.py`: coleta de níveis e propagação da maré.
- `ferramentas/`: geradores das páginas e extração de dados.
- `README.md`: descrição de cada parte e como rodar.
