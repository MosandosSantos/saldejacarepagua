-- ============================================================
-- CRMCronos.Cloud — Inicialização do banco PostgreSQL
-- Rodar com: psql -U postgres -h localhost -f init-db.sql
-- ============================================================

-- Cria o banco se não existir (truque psql)
SELECT 'CREATE DATABASE cronoscrm'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'cronoscrm')\gexec

\c cronoscrm

-- ============================================================
-- TABELAS
-- ============================================================
CREATE TABLE IF NOT EXISTS contatos (
  id         SERIAL PRIMARY KEY,
  nome       TEXT NOT NULL,
  empresa    TEXT NOT NULL DEFAULT '—',
  tel        TEXT NOT NULL DEFAULT '—',
  email      TEXT NOT NULL DEFAULT '—',
  seg        TEXT NOT NULL,
  stage      TEXT NOT NULL,
  valor      NUMERIC(12,2) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- SEED — 20 contatos fictícios (id 1..20)
-- ============================================================
INSERT INTO contatos (id, nome, empresa, tel, email, seg, stage, valor) VALUES
  (1,  'Mariana Fontes',     'Clínica Vitalys',           '(11) 98421-3390', 'mariana@vitalys.com.br',      'clinica',     'proposta',    14500),
  (2,  'Ricardo Almeida',    'Almeida Advogados',         '(21) 99187-4402', 'ricardo@almeidaadv.com.br',   'advocacia',   'negociacao',  22800),
  (3,  'Juliana Prado',      'Prado Imóveis',             '(31) 98765-1120', 'juliana@pradoimoveis.com.br', 'imobiliaria', 'novo',        9800),
  (4,  'Fernando Rocha',     'RochaTech Distribuidora',   '(41) 99340-8871', 'fernando@rochatech.com.br',   'varejo',      'contato',     6400),
  (5,  'Camila Bittencourt', 'Studio Bitt Marketing',     '(11) 97655-2213', 'camila@studiobitt.com.br',    'agencia',     'fechado',     18700),
  (6,  'Thiago Nogueira',    'Nogueira Metalúrgica',      '(51) 98230-6654', 'thiago@nogueirametal.com.br', 'industria',   'proposta',    24500),
  (7,  'Patrícia Lemos',     'Espaço Lemos Odonto',       '(85) 99123-7788', 'patricia@lemosodonto.com.br', 'clinica',     'novo',        3200),
  (8,  'Gustavo Siqueira',   'Siqueira & Cia Contábil',   '(11) 98900-3345', 'gustavo@siqueiracia.com.br',  'advocacia',   'contato',     5600),
  (9,  'Beatriz Antunes',    'Antunes Cursos Livres',     '(19) 99450-1198', 'beatriz@antunescursos.com.br','educacao',    'qualificado', 8100),
  (10, 'Rafael Monteiro',    'Monteiro Auto Center',      '(47) 98112-4471', 'rafael@monteiroauto.com.br',  'varejo',      'novo',        11200),
  (11, 'Larissa Coelho',     'Coelho Imobiliária Prime',  '(62) 99677-2205', 'larissa@coelhoprime.com.br',  'imobiliaria', 'novo',        16900),
  (12, 'Eduardo Vasques',    'Vasques Digital',           '(11) 98544-9910', 'eduardo@vasquesdigital.com',  'agencia',     'fechado',     12400),
  (13, 'Isabela Freitas',    'Freitas Estética Avançada', '(81) 99320-6612', 'isabela@freitasestetica.com', 'clinica',     'contato',     7300),
  (14, 'Marcelo Tavares',    'Tavares Advocacia Empres.', '(11) 97880-1123', 'marcelo@tavaresadv.com.br',   'advocacia',   'qualificado', 19500),
  (15, 'Aline Barros',       'Barros Moda & Estilo',      '(21) 98455-7789', 'aline@barrosmoda.com.br',     'varejo',      'novo',        2800),
  (16, 'Vinícius Duarte',    'Duarte Engenharia',         '(31) 99012-3348', 'vinicius@duarteeng.com.br',   'industria',   'negociacao',  25000),
  (17, 'Carolina Neves',     'Neves Idiomas',             '(11) 98233-4471', 'carolina@nevesidiomas.com.br','educacao',    'perdido',     4900),
  (18, 'Bruno Carvalho',     'Carvalho Imóveis Litoral',  '(13) 99188-5560', 'bruno@carvalholitoral.com.br','imobiliaria', 'proposta',    13600),
  (19, 'Renata Machado',     'Machado Odontologia',       '(41) 98700-2214', 'renata@machadoodonto.com.br', 'clinica',     'contato',     6800),
  (20, 'Leandro Pires',      'Pires Performance Ads',     '(11) 99544-8823', 'leandro@piresads.com.br',     'agencia',     'qualificado', 15300)
ON CONFLICT (id) DO NOTHING;

-- updated_at em ordem de id (id maior = mais recente) — espelha "8 maiores ids"
UPDATE contatos SET updated_at = NOW() - (21 - id) * INTERVAL '1 second';

-- Reseta a sequência do SERIAL
SELECT setval('contatos_id_seq', (SELECT MAX(id) FROM contatos));

-- ============================================================
-- Confirmação
-- ============================================================
SELECT 'CRMCronos.Cloud pronto!' AS status,
       (SELECT COUNT(*) FROM contatos) AS contatos;
