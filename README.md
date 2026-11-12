# Raio-X de Hortolândia

Site independente que mostra, com dados oficiais da Câmara Municipal de Hortolândia-SP,
o que cada vereador fez desde 2025: presença, propostas e votos.

- `site/` é o site publicado (`index.html` e `dados.js`).
- `robo/atualizar.py` coleta os dados no sistema legislativo da Câmara e gera `site/dados.js`.
- `.github/workflows/atualizar.yml` roda o robô todo dia e publica o site.

Se a coleta falhar ou vier incompleta, o robô para e o site continua com a última versão boa.
O GitHub avisa por e-mail quando uma execução falha.

Não tem vínculo com a Câmara, com a Prefeitura ou com partido.
