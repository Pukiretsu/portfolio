# SendFast Analytics: dados de entregas na AWS

Criei uma plataforma de análise na AWS para um negócio simulado de entregas de comida. O SendFast conecta uma interface de pedidos autenticada ao armazenamento transacional, a um pipeline agendado de data lake e a painéis baseados em consultas SQL, com Terraform e GitHub Actions para gerenciar infraestrutura e implantação.

## Acesso web seguro e ingestão de pedidos

O frontend em React, TypeScript e Vite é entregue pelo CloudFront a partir de um bucket S3 privado com Origin Access Control. O AWS WAF protege a distribuição do CloudFront, enquanto o Cognito autentica os usuários e um autorizador JWT do API Gateway protege a API de ingestão.

Uma Lambda em Python valida os pedidos, normaliza as datas para UTC, grava cada pedido no DynamoDB e salva uma cópia em JSON na camada Raw do S3. Os pedidos incluem tempo de entrega, valor, região, estado e forma de pagamento, fornecendo as entradas para os relatórios do negócio.

## ETL agendado e um data lake consultável

O EventBridge agenda uma Lambda ETL separada que usa pandas e AWS SDK for pandas. O processo mantém um checkpoint, identifica os dias afetados, normaliza os tipos das colunas e elimina duplicatas por identificador de pedido antes de gravar Parquet na camada Stage do S3.

O conjunto de dados Parquet é particionado por ano, mês e dia e registrado no Glue Data Catalog. As partições diárias alteradas são sobrescritas, e o checkpoint avança após a conclusão da gravação e das atualizações do catálogo. O Athena consulta esse conjunto de dados e armazena os resultados das consultas em outro bucket S3.

## Grafana e acesso operacional

O Grafana roda em Docker no EC2, com o datasource do Athena configurado durante a inicialização da instância. As credenciais de administração são recuperadas do AWS Secrets Manager por meio do perfil da instância. O acesso ao Grafana é restrito aos intervalos CIDR configurados, e o SSH fica desabilitado por padrão.

Assim, a interface pública de pedidos, a API de ingestão, o armazenamento analítico e o acesso ao painel ficam separados em componentes distintos.

## Infraestrutura e CI/CD

Módulos reutilizáveis do Terraform definem a entrega web, WAF, Cognito, API Gateway, funções Lambda, DynamoDB, S3, EventBridge, Glue, Athena e os recursos do Grafana.

O GitHub Actions verifica a formatação e a validade do Terraform, executa lint e testes dos handlers Lambda e verifica o TypeScript e a compilação web. A implantação usa credenciais AWS via OIDC, aplica o Terraform e exporta seus outputs para gerar a configuração de produção do frontend. Em seguida, o pipeline compila a aplicação, publica os arquivos no S3 e invalida o CloudFront.

O projeto demonstra o caminho completo de um evento de aplicação até um relatório analítico, incluindo validação, processamento incremental, controle de acesso e implantação automatizada.
