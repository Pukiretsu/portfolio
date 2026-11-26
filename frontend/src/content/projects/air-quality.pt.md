# Qair: alertas de qualidade do ar em Bogotá

Participei de um projeto universitário que transforma medições de PM2.5 de Bogotá em alertas de qualidade do ar por estação. O Qair combina coleta automatizada, um motor de cálculo rastreável em Python e um mapa interativo para explorar resultados e baixar os cálculos que os fundamentam.

## Dos relatórios do SISAIRE aos alertas por estação

Os usuários podem enviar medições em CSV ou Excel ou solicitar relatórios do SISAIRE por meio de automação do navegador com Playwright. O backend consolida os relatórios e usa um catálogo CAR/SISAIRE para completar as coordenadas das estações.

O motor em pandas calcula uma média móvel de 24 horas para as medições horárias, exigindo 18 leituras válidas por padrão. Quando um relatório diário já contém uma média agregada, esse valor é usado diretamente. Os níveis candidatos são avaliados nas 48 leituras seguintes, com um critério de persistência superior a 75%. Cada execução gera registros de cálculo em CSV e Excel, um resumo por estação e um GeoJSON para o mapa.

Essas são as regras implementadas pelo projeto; o painel apresenta os resultados e disponibiliza os registros de cálculo para consulta.

## Uma API com sessões de cálculo persistentes

O FastAPI expõe endpoints de cálculo manual e amostragem automática. Os trabalhos em segundo plano informam estado, progresso, etapa atual, eventos e erros, permitindo acompanhar uma execução e consultar resultados anteriores.

O SQLAlchemy mantém o histórico em SQLite no desenvolvimento local ou em PostgreSQL quando a conexão é configurada. O backend também oferece catálogos de estações, verificações de saúde e endpoints para baixar os arquivos gerados.

## Painel React e mapas

O frontend usa React, Vite, Tailwind CSS e Leaflet. Ele reúne envio de arquivos, filtros de estações e datas para amostragem, acompanhamento do progresso, um painel de histórico de sessões e o mapa de resultados. O GeoJSON conecta as saídas do Python aos marcadores das estações e ao estado calculado de cada uma.

## Implantação com contêineres na AWS

A infraestrutura Terraform define um frontend em S3 privado atrás do CloudFront com Origin Access Control. As requisições a `/api/*` passam por um Application Load Balancer até o FastAPI no ECS Fargate.

O ECR armazena a imagem do backend, o RDS PostgreSQL mantém as sessões de cálculo e o EFS criptografado preserva os arquivos gerados. O ECS recebe a conexão do banco pelo Secrets Manager e envia os logs da aplicação ao CloudWatch. O Docker Compose oferece um ambiente local para a API e o PostgreSQL.

## Validação e entrega

O GitHub Actions executa Ruff e Pytest no backend Python e compila a aplicação React usando o lockfile do npm. Scripts separados publicam a imagem do backend no ECR e implantam o frontend no S3 com invalidação do CloudFront.

O projeto conecta ingestão de dados, cálculos reproduzíveis, desenvolvimento de API, visualização SIG e infraestrutura como código em um único fluxo.
