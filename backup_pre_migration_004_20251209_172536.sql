--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13
-- Dumped by pg_dump version 15.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: timescaledb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: asset_type; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.asset_type AS ENUM (
    'STOCK',
    'OPTION',
    'CRYPTO',
    'FUTURE'
);


ALTER TYPE public.asset_type OWNER TO kapman;

--
-- Name: option_strategy; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.option_strategy AS ENUM (
    'LONG_CALL',
    'LONG_PUT',
    'CSP',
    'VERTICAL_SPREAD'
);


ALTER TYPE public.option_strategy OWNER TO kapman;

--
-- Name: option_type; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.option_type AS ENUM (
    'C',
    'P'
);


ALTER TYPE public.option_type OWNER TO kapman;

--
-- Name: order_side; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.order_side AS ENUM (
    'BUY',
    'SELL'
);


ALTER TYPE public.order_side OWNER TO kapman;

--
-- Name: order_status; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.order_status AS ENUM (
    'OPEN',
    'FILLED',
    'PARTIALLY_FILLED',
    'CANCELLED',
    'REJECTED'
);


ALTER TYPE public.order_status OWNER TO kapman;

--
-- Name: order_type; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.order_type AS ENUM (
    'MARKET',
    'LIMIT',
    'STOP',
    'STOP_LIMIT',
    'TRAILING_STOP'
);


ALTER TYPE public.order_type OWNER TO kapman;

--
-- Name: outcome_status; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.outcome_status AS ENUM (
    'WIN',
    'LOSS',
    'NEUTRAL'
);


ALTER TYPE public.outcome_status OWNER TO kapman;

--
-- Name: position_side; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.position_side AS ENUM (
    'LONG',
    'SHORT'
);


ALTER TYPE public.position_side OWNER TO kapman;

--
-- Name: recommendation_action; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.recommendation_action AS ENUM (
    'BUY',
    'SELL',
    'HOLD',
    'HEDGE'
);


ALTER TYPE public.recommendation_action OWNER TO kapman;

--
-- Name: recommendation_direction; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.recommendation_direction AS ENUM (
    'LONG',
    'SHORT',
    'NEUTRAL'
);


ALTER TYPE public.recommendation_direction OWNER TO kapman;

--
-- Name: recommendation_status; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.recommendation_status AS ENUM (
    'active',
    'closed',
    'expired'
);


ALTER TYPE public.recommendation_status OWNER TO kapman;

--
-- Name: signal_type; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.signal_type AS ENUM (
    'ENTRY',
    'EXIT',
    'STOP_LOSS',
    'TAKE_PROFIT'
);


ALTER TYPE public.signal_type OWNER TO kapman;

--
-- Name: strategy_type; Type: TYPE; Schema: public; Owner: kapman
--

CREATE TYPE public.strategy_type AS ENUM (
    'MOMENTUM',
    'MEAN_REVERSION',
    'ARBITRAGE',
    'MARKET_MAKING',
    'HEDGING'
);


ALTER TYPE public.strategy_type OWNER TO kapman;

--
-- Name: update_modified_column(); Type: FUNCTION; Schema: public; Owner: kapman
--

CREATE FUNCTION public.update_modified_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_modified_column() OWNER TO kapman;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _compressed_hypertable_10; Type: TABLE; Schema: _timescaledb_internal; Owner: kapman
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_10 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_10 OWNER TO kapman;

--
-- Name: _compressed_hypertable_11; Type: TABLE; Schema: _timescaledb_internal; Owner: kapman
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_11 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_11 OWNER TO kapman;

--
-- Name: _compressed_hypertable_12; Type: TABLE; Schema: _timescaledb_internal; Owner: kapman
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_12 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_12 OWNER TO kapman;

--
-- Name: _compressed_hypertable_7; Type: TABLE; Schema: _timescaledb_internal; Owner: kapman
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_7 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_7 OWNER TO kapman;

--
-- Name: _compressed_hypertable_8; Type: TABLE; Schema: _timescaledb_internal; Owner: kapman
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_8 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_8 OWNER TO kapman;

--
-- Name: _compressed_hypertable_9; Type: TABLE; Schema: _timescaledb_internal; Owner: kapman
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_9 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_9 OWNER TO kapman;

--
-- Name: market_data; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.market_data (
    "time" timestamp with time zone NOT NULL,
    asset_id uuid NOT NULL,
    open numeric(20,8) NOT NULL,
    high numeric(20,8) NOT NULL,
    low numeric(20,8) NOT NULL,
    close numeric(20,8) NOT NULL,
    volume numeric(20,8) NOT NULL,
    vwap numeric(20,8),
    trade_count integer
);


ALTER TABLE public.market_data OWNER TO kapman;

--
-- Name: _direct_view_13; Type: VIEW; Schema: _timescaledb_internal; Owner: kapman
--

CREATE VIEW _timescaledb_internal._direct_view_13 AS
 SELECT public.time_bucket('1 day'::interval, market_data."time") AS bucket,
    market_data.asset_id,
    public.first(market_data.open, market_data."time") AS open,
    max(market_data.high) AS high,
    min(market_data.low) AS low,
    public.last(market_data.close, market_data."time") AS close,
    sum(market_data.volume) AS volume,
    (sum((market_data.volume * market_data.vwap)) / NULLIF(sum(market_data.volume), (0)::numeric)) AS vwap,
    sum(market_data.trade_count) AS trade_count
   FROM public.market_data
  GROUP BY (public.time_bucket('1 day'::interval, market_data."time")), market_data.asset_id;


ALTER TABLE _timescaledb_internal._direct_view_13 OWNER TO kapman;

--
-- Name: _direct_view_14; Type: VIEW; Schema: _timescaledb_internal; Owner: kapman
--

CREATE VIEW _timescaledb_internal._direct_view_14 AS
 SELECT public.time_bucket('01:00:00'::interval, market_data."time") AS bucket,
    market_data.asset_id,
    public.first(market_data.open, market_data."time") AS open,
    max(market_data.high) AS high,
    min(market_data.low) AS low,
    public.last(market_data.close, market_data."time") AS close,
    sum(market_data.volume) AS volume,
    (sum((market_data.volume * market_data.vwap)) / NULLIF(sum(market_data.volume), (0)::numeric)) AS vwap,
    sum(market_data.trade_count) AS trade_count
   FROM public.market_data
  GROUP BY (public.time_bucket('01:00:00'::interval, market_data."time")), market_data.asset_id;


ALTER TABLE _timescaledb_internal._direct_view_14 OWNER TO kapman;

--
-- Name: ohlcv_daily; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.ohlcv_daily (
    "time" timestamp with time zone NOT NULL,
    symbol_id uuid NOT NULL,
    open numeric(12,4) NOT NULL,
    high numeric(12,4) NOT NULL,
    low numeric(12,4) NOT NULL,
    close numeric(12,4) NOT NULL,
    volume bigint NOT NULL,
    vwap numeric(12,4),
    source character varying(50) DEFAULT 'polygon_s3'::character varying
);


ALTER TABLE public.ohlcv_daily OWNER TO kapman;

--
-- Name: _hyper_1_1_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: kapman
--

CREATE TABLE _timescaledb_internal._hyper_1_1_chunk (
    CONSTRAINT constraint_1 CHECK ((("time" >= '2024-12-05 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-12-12 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_daily);


ALTER TABLE _timescaledb_internal._hyper_1_1_chunk OWNER TO kapman;

--
-- Name: _materialized_hypertable_13; Type: TABLE; Schema: _timescaledb_internal; Owner: kapman
--

CREATE TABLE _timescaledb_internal._materialized_hypertable_13 (
    bucket timestamp with time zone NOT NULL,
    asset_id uuid,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    volume numeric,
    vwap numeric,
    trade_count bigint
);


ALTER TABLE _timescaledb_internal._materialized_hypertable_13 OWNER TO kapman;

--
-- Name: _materialized_hypertable_14; Type: TABLE; Schema: _timescaledb_internal; Owner: kapman
--

CREATE TABLE _timescaledb_internal._materialized_hypertable_14 (
    bucket timestamp with time zone NOT NULL,
    asset_id uuid,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    volume numeric,
    vwap numeric,
    trade_count bigint
);


ALTER TABLE _timescaledb_internal._materialized_hypertable_14 OWNER TO kapman;

--
-- Name: _partial_view_13; Type: VIEW; Schema: _timescaledb_internal; Owner: kapman
--

CREATE VIEW _timescaledb_internal._partial_view_13 AS
 SELECT public.time_bucket('1 day'::interval, market_data."time") AS bucket,
    market_data.asset_id,
    public.first(market_data.open, market_data."time") AS open,
    max(market_data.high) AS high,
    min(market_data.low) AS low,
    public.last(market_data.close, market_data."time") AS close,
    sum(market_data.volume) AS volume,
    (sum((market_data.volume * market_data.vwap)) / NULLIF(sum(market_data.volume), (0)::numeric)) AS vwap,
    sum(market_data.trade_count) AS trade_count
   FROM public.market_data
  GROUP BY (public.time_bucket('1 day'::interval, market_data."time")), market_data.asset_id;


ALTER TABLE _timescaledb_internal._partial_view_13 OWNER TO kapman;

--
-- Name: _partial_view_14; Type: VIEW; Schema: _timescaledb_internal; Owner: kapman
--

CREATE VIEW _timescaledb_internal._partial_view_14 AS
 SELECT public.time_bucket('01:00:00'::interval, market_data."time") AS bucket,
    market_data.asset_id,
    public.first(market_data.open, market_data."time") AS open,
    max(market_data.high) AS high,
    min(market_data.low) AS low,
    public.last(market_data.close, market_data."time") AS close,
    sum(market_data.volume) AS volume,
    (sum((market_data.volume * market_data.vwap)) / NULLIF(sum(market_data.volume), (0)::numeric)) AS vwap,
    sum(market_data.trade_count) AS trade_count
   FROM public.market_data
  GROUP BY (public.time_bucket('01:00:00'::interval, market_data."time")), market_data.asset_id;


ALTER TABLE _timescaledb_internal._partial_view_14 OWNER TO kapman;

--
-- Name: accounts; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.accounts (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    name text NOT NULL,
    broker_name text NOT NULL,
    api_key text,
    api_secret text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.accounts OWNER TO kapman;

--
-- Name: assets; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.assets (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    symbol text NOT NULL,
    name text,
    exchange_id uuid,
    type public.asset_type NOT NULL,
    is_active boolean DEFAULT true,
    min_price_increment numeric(12,6),
    min_order_size numeric(12,6),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.assets OWNER TO kapman;

--
-- Name: daily_snapshots; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.daily_snapshots (
    "time" timestamp with time zone NOT NULL,
    symbol_id uuid NOT NULL,
    wyckoff_phase character varying(1),
    phase_confidence numeric(4,3),
    phase_sub_stage character varying(10),
    events_detected text[],
    primary_event character varying(20),
    primary_event_confidence numeric(4,3),
    bc_score integer,
    spring_score integer,
    composite_score numeric(4,2),
    volatility_regime character varying(20),
    checklist_json jsonb,
    technical_indicators jsonb,
    dealer_metrics jsonb,
    price_metrics jsonb,
    model_version character varying(50),
    data_quality character varying(20),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT daily_snapshots_bc_score_check CHECK (((bc_score >= 0) AND (bc_score <= 28))),
    CONSTRAINT daily_snapshots_phase_confidence_check CHECK (((phase_confidence >= (0)::numeric) AND (phase_confidence <= (1)::numeric))),
    CONSTRAINT daily_snapshots_spring_score_check CHECK (((spring_score >= 0) AND (spring_score <= 12))),
    CONSTRAINT daily_snapshots_wyckoff_phase_check CHECK (((wyckoff_phase)::text = ANY ((ARRAY['A'::character varying, 'B'::character varying, 'C'::character varying, 'D'::character varying, 'E'::character varying])::text[])))
);


ALTER TABLE public.daily_snapshots OWNER TO kapman;

--
-- Name: exchanges; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.exchanges (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name text NOT NULL,
    code text NOT NULL,
    country text,
    timezone text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.exchanges OWNER TO kapman;

--
-- Name: job_runs; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.job_runs (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    job_name character varying(100) NOT NULL,
    started_at timestamp with time zone NOT NULL,
    completed_at timestamp with time zone,
    status character varying(20) NOT NULL,
    tickers_processed integer DEFAULT 0,
    errors_json jsonb,
    duration_seconds integer,
    metadata jsonb
);


ALTER TABLE public.job_runs OWNER TO kapman;

--
-- Name: market_data_daily; Type: VIEW; Schema: public; Owner: kapman
--

CREATE VIEW public.market_data_daily AS
 SELECT _materialized_hypertable_13.bucket,
    _materialized_hypertable_13.asset_id,
    _materialized_hypertable_13.open,
    _materialized_hypertable_13.high,
    _materialized_hypertable_13.low,
    _materialized_hypertable_13.close,
    _materialized_hypertable_13.volume,
    _materialized_hypertable_13.vwap,
    _materialized_hypertable_13.trade_count
   FROM _timescaledb_internal._materialized_hypertable_13;


ALTER TABLE public.market_data_daily OWNER TO kapman;

--
-- Name: market_data_hourly; Type: VIEW; Schema: public; Owner: kapman
--

CREATE VIEW public.market_data_hourly AS
 SELECT _materialized_hypertable_14.bucket,
    _materialized_hypertable_14.asset_id,
    _materialized_hypertable_14.open,
    _materialized_hypertable_14.high,
    _materialized_hypertable_14.low,
    _materialized_hypertable_14.close,
    _materialized_hypertable_14.volume,
    _materialized_hypertable_14.vwap,
    _materialized_hypertable_14.trade_count
   FROM _timescaledb_internal._materialized_hypertable_14;


ALTER TABLE public.market_data_hourly OWNER TO kapman;

--
-- Name: model_parameters; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.model_parameters (
    id integer NOT NULL,
    model_name character varying(100) NOT NULL,
    version character varying(50) NOT NULL,
    parameters_json jsonb NOT NULL,
    effective_from timestamp with time zone DEFAULT now() NOT NULL,
    effective_to timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.model_parameters OWNER TO kapman;

--
-- Name: model_parameters_id_seq; Type: SEQUENCE; Schema: public; Owner: kapman
--

CREATE SEQUENCE public.model_parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.model_parameters_id_seq OWNER TO kapman;

--
-- Name: model_parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: kapman
--

ALTER SEQUENCE public.model_parameters_id_seq OWNED BY public.model_parameters.id;


--
-- Name: options_chains; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.options_chains (
    "time" timestamp with time zone NOT NULL,
    symbol_id uuid NOT NULL,
    expiration_date date NOT NULL,
    strike_price numeric(12,4) NOT NULL,
    option_type public.option_type NOT NULL,
    bid numeric(12,4),
    ask numeric(12,4),
    last numeric(12,4),
    volume integer,
    open_interest integer,
    implied_volatility numeric(10,6),
    delta numeric(10,6),
    gamma numeric(10,6),
    theta numeric(10,6),
    vega numeric(10,6)
);


ALTER TABLE public.options_chains OWNER TO kapman;

--
-- Name: order_book_snapshots; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.order_book_snapshots (
    "time" timestamp with time zone NOT NULL,
    asset_id uuid NOT NULL,
    bid_price_1 numeric(20,8),
    bid_size_1 numeric(20,8),
    ask_price_1 numeric(20,8),
    ask_size_1 numeric(20,8)
);


ALTER TABLE public.order_book_snapshots OWNER TO kapman;

--
-- Name: orders; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.orders (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    account_id uuid NOT NULL,
    portfolio_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    client_order_id text,
    exchange_order_id text,
    type public.order_type NOT NULL,
    side public.order_side NOT NULL,
    quantity numeric(20,8) NOT NULL,
    price numeric(20,8),
    stop_price numeric(20,8),
    time_in_force text DEFAULT 'GTC'::text,
    status public.order_status NOT NULL,
    filled_quantity numeric(20,8) DEFAULT 0,
    average_fill_price numeric(20,8),
    commission numeric(20,8) DEFAULT 0,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    filled_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    notes text
);


ALTER TABLE public.orders OWNER TO kapman;

--
-- Name: portfolio_tickers; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.portfolio_tickers (
    portfolio_id uuid NOT NULL,
    ticker_id uuid NOT NULL,
    priority character varying(10),
    added_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT portfolio_tickers_priority_check CHECK (((priority)::text = ANY ((ARRAY['P0'::character varying, 'P1'::character varying, 'P2'::character varying, 'P3'::character varying])::text[])))
);


ALTER TABLE public.portfolio_tickers OWNER TO kapman;

--
-- Name: portfolios; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.portfolios (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.portfolios OWNER TO kapman;

--
-- Name: positions; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.positions (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    account_id uuid NOT NULL,
    portfolio_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    quantity numeric(20,8) NOT NULL,
    side public.position_side NOT NULL,
    average_entry_price numeric(20,8) NOT NULL,
    current_price numeric(20,8),
    unrealized_pnl numeric(20,8) DEFAULT 0,
    realized_pnl numeric(20,8) DEFAULT 0,
    is_open boolean DEFAULT true,
    opened_at timestamp with time zone DEFAULT now() NOT NULL,
    closed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.positions OWNER TO kapman;

--
-- Name: recommendation_outcomes; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.recommendation_outcomes (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    recommendation_id uuid,
    evaluation_date date NOT NULL,
    evaluation_window_days integer,
    entry_price_actual numeric(12,4),
    exit_price_actual numeric(12,4),
    high_price_during_window numeric(12,4),
    low_price_during_window numeric(12,4),
    days_to_target integer,
    days_to_stop integer,
    days_held integer,
    max_favorable_excursion numeric(8,4),
    max_adverse_excursion numeric(8,4),
    direction_correct boolean,
    predicted_confidence numeric(4,3),
    directional_brier numeric(6,4),
    actual_return_pct numeric(8,4),
    hit_profit_target boolean,
    hit_stop_loss boolean,
    success_score_v1 numeric(4,3),
    outcome_status public.outcome_status,
    notes text,
    evaluated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.recommendation_outcomes OWNER TO kapman;

--
-- Name: recommendations; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.recommendations (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    snapshot_time timestamp with time zone NOT NULL,
    symbol_id uuid,
    recommendation_date date NOT NULL,
    direction public.recommendation_direction NOT NULL,
    action public.recommendation_action NOT NULL,
    confidence numeric(4,3),
    justification text,
    entry_price_target numeric(12,4),
    stop_loss numeric(12,4),
    profit_target numeric(12,4),
    risk_reward_ratio numeric(6,2),
    option_strike numeric(12,4),
    option_expiration date,
    option_type public.option_type,
    option_strategy public.option_strategy,
    status public.recommendation_status DEFAULT 'active'::public.recommendation_status,
    model_version character varying(50),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT recommendations_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))
);


ALTER TABLE public.recommendations OWNER TO kapman;

--
-- Name: signals; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.signals (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    strategy_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    type public.signal_type NOT NULL,
    strength numeric(5,2),
    price_target numeric(20,8),
    stop_loss numeric(20,8),
    notes text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT signals_strength_check CHECK (((strength >= (0)::numeric) AND (strength <= (100)::numeric)))
);


ALTER TABLE public.signals OWNER TO kapman;

--
-- Name: strategies; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.strategies (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    name text NOT NULL,
    type public.strategy_type NOT NULL,
    description text,
    parameters jsonb,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.strategies OWNER TO kapman;

--
-- Name: tickers; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.tickers (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    symbol character varying(20) NOT NULL,
    name character varying(255),
    sector character varying(100),
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.tickers OWNER TO kapman;

--
-- Name: trade_history; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.trade_history (
    "time" timestamp with time zone NOT NULL,
    asset_id uuid NOT NULL,
    price numeric(20,8) NOT NULL,
    quantity numeric(20,8) NOT NULL,
    side public.order_side,
    is_buyer_maker boolean,
    trade_id bigint NOT NULL
);


ALTER TABLE public.trade_history OWNER TO kapman;

--
-- Name: trades; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.trades (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    account_id uuid NOT NULL,
    portfolio_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    quantity numeric(20,8) NOT NULL,
    price numeric(20,8) NOT NULL,
    side public.order_side NOT NULL,
    fee numeric(20,8) DEFAULT 0,
    fee_asset text,
    realized_pnl numeric(20,8) DEFAULT 0,
    strategy_id text,
    signal_id text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.trades OWNER TO kapman;

--
-- Name: users; Type: TABLE; Schema: public; Owner: kapman
--

CREATE TABLE public.users (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    email text NOT NULL,
    hashed_password text NOT NULL,
    first_name text,
    last_name text,
    is_active boolean DEFAULT true,
    is_verified boolean DEFAULT false,
    last_login timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.users OWNER TO kapman;

--
-- Name: _hyper_1_1_chunk source; Type: DEFAULT; Schema: _timescaledb_internal; Owner: kapman
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk ALTER COLUMN source SET DEFAULT 'polygon_s3'::character varying;


--
-- Name: model_parameters id; Type: DEFAULT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.model_parameters ALTER COLUMN id SET DEFAULT nextval('public.model_parameters_id_seq'::regclass);


--
-- Data for Name: hypertable; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.hypertable (id, schema_name, table_name, associated_schema_name, associated_table_prefix, num_dimensions, chunk_sizing_func_schema, chunk_sizing_func_name, chunk_target_size, compression_state, compressed_hypertable_id, status) FROM stdin;
7	_timescaledb_internal	_compressed_hypertable_7	_timescaledb_internal	_hyper_7	0	_timescaledb_functions	calculate_chunk_interval	0	2	\N	0
4	public	market_data	_timescaledb_internal	_hyper_4	1	_timescaledb_functions	calculate_chunk_interval	0	1	7	0
8	_timescaledb_internal	_compressed_hypertable_8	_timescaledb_internal	_hyper_8	0	_timescaledb_functions	calculate_chunk_interval	0	2	\N	0
5	public	order_book_snapshots	_timescaledb_internal	_hyper_5	1	_timescaledb_functions	calculate_chunk_interval	0	1	8	0
9	_timescaledb_internal	_compressed_hypertable_9	_timescaledb_internal	_hyper_9	0	_timescaledb_functions	calculate_chunk_interval	0	2	\N	0
6	public	trade_history	_timescaledb_internal	_hyper_6	1	_timescaledb_functions	calculate_chunk_interval	0	1	9	0
10	_timescaledb_internal	_compressed_hypertable_10	_timescaledb_internal	_hyper_10	0	_timescaledb_functions	calculate_chunk_interval	0	2	\N	0
1	public	ohlcv_daily	_timescaledb_internal	_hyper_1	1	_timescaledb_functions	calculate_chunk_interval	0	1	10	0
11	_timescaledb_internal	_compressed_hypertable_11	_timescaledb_internal	_hyper_11	0	_timescaledb_functions	calculate_chunk_interval	0	2	\N	0
2	public	options_chains	_timescaledb_internal	_hyper_2	1	_timescaledb_functions	calculate_chunk_interval	0	1	11	0
12	_timescaledb_internal	_compressed_hypertable_12	_timescaledb_internal	_hyper_12	0	_timescaledb_functions	calculate_chunk_interval	0	2	\N	0
3	public	daily_snapshots	_timescaledb_internal	_hyper_3	1	_timescaledb_functions	calculate_chunk_interval	0	1	12	0
13	_timescaledb_internal	_materialized_hypertable_13	_timescaledb_internal	_hyper_13	1	_timescaledb_functions	calculate_chunk_interval	0	0	\N	0
14	_timescaledb_internal	_materialized_hypertable_14	_timescaledb_internal	_hyper_14	1	_timescaledb_functions	calculate_chunk_interval	0	0	\N	0
\.


--
-- Data for Name: chunk; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.chunk (id, hypertable_id, schema_name, table_name, compressed_chunk_id, dropped, status, osm_chunk, creation_time) FROM stdin;
1	1	_timescaledb_internal	_hyper_1_1_chunk	\N	f	0	f	2025-12-09 00:45:40.921634+00
\.


--
-- Data for Name: chunk_column_stats; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.chunk_column_stats (id, hypertable_id, chunk_id, column_name, range_start, range_end, valid) FROM stdin;
\.


--
-- Data for Name: dimension; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.dimension (id, hypertable_id, column_name, column_type, aligned, num_slices, partitioning_func_schema, partitioning_func, interval_length, compress_interval_length, integer_now_func_schema, integer_now_func) FROM stdin;
1	1	time	timestamp with time zone	t	\N	\N	\N	604800000000	\N	\N	\N
2	2	time	timestamp with time zone	t	\N	\N	\N	604800000000	\N	\N	\N
3	3	time	timestamp with time zone	t	\N	\N	\N	604800000000	\N	\N	\N
4	4	time	timestamp with time zone	t	\N	\N	\N	604800000000	\N	\N	\N
5	5	time	timestamp with time zone	t	\N	\N	\N	604800000000	\N	\N	\N
6	6	time	timestamp with time zone	t	\N	\N	\N	604800000000	\N	\N	\N
7	13	bucket	timestamp with time zone	t	\N	\N	\N	6048000000000	\N	\N	\N
8	14	bucket	timestamp with time zone	t	\N	\N	\N	6048000000000	\N	\N	\N
\.


--
-- Data for Name: dimension_slice; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.dimension_slice (id, dimension_id, range_start, range_end) FROM stdin;
1	1	1733356800000000	1733961600000000
\.


--
-- Data for Name: chunk_constraint; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.chunk_constraint (chunk_id, dimension_slice_id, constraint_name, hypertable_constraint_name) FROM stdin;
1	1	constraint_1	\N
1	\N	1_1_ohlcv_daily_pkey	ohlcv_daily_pkey
1	\N	1_2_ohlcv_daily_symbol_id_fkey	ohlcv_daily_symbol_id_fkey
\.


--
-- Data for Name: compression_chunk_size; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.compression_chunk_size (chunk_id, compressed_chunk_id, uncompressed_heap_size, uncompressed_toast_size, uncompressed_index_size, compressed_heap_size, compressed_toast_size, compressed_index_size, numrows_pre_compression, numrows_post_compression, numrows_frozen_immediately) FROM stdin;
\.


--
-- Data for Name: compression_settings; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.compression_settings (relid, compress_relid, segmentby, orderby, orderby_desc, orderby_nullsfirst, index) FROM stdin;
public.market_data	\N	{asset_id}	\N	\N	\N	\N
public.order_book_snapshots	\N	{asset_id}	\N	\N	\N	\N
public.trade_history	\N	{asset_id}	\N	\N	\N	\N
public.ohlcv_daily	\N	{symbol_id}	\N	\N	\N	\N
public.options_chains	\N	{symbol_id,expiration_date,strike_price,option_type}	\N	\N	\N	\N
public.daily_snapshots	\N	{symbol_id}	\N	\N	\N	\N
\.


--
-- Data for Name: continuous_agg; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.continuous_agg (mat_hypertable_id, raw_hypertable_id, parent_mat_hypertable_id, user_view_schema, user_view_name, partial_view_schema, partial_view_name, direct_view_schema, direct_view_name, materialized_only, finalized) FROM stdin;
13	4	\N	public	market_data_daily	_timescaledb_internal	_partial_view_13	_timescaledb_internal	_direct_view_13	t	t
14	4	\N	public	market_data_hourly	_timescaledb_internal	_partial_view_14	_timescaledb_internal	_direct_view_14	t	t
\.


--
-- Data for Name: continuous_agg_migrate_plan; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.continuous_agg_migrate_plan (mat_hypertable_id, start_ts, end_ts, user_view_definition) FROM stdin;
\.


--
-- Data for Name: continuous_agg_migrate_plan_step; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.continuous_agg_migrate_plan_step (mat_hypertable_id, step_id, status, start_ts, end_ts, type, config) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_bucket_function; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.continuous_aggs_bucket_function (mat_hypertable_id, bucket_func, bucket_width, bucket_origin, bucket_offset, bucket_timezone, bucket_fixed_width) FROM stdin;
13	public.time_bucket(interval,timestamp with time zone)	1 day	\N	\N	\N	t
14	public.time_bucket(interval,timestamp with time zone)	01:00:00	\N	\N	\N	t
\.


--
-- Data for Name: continuous_aggs_hypertable_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.continuous_aggs_hypertable_invalidation_log (hypertable_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_invalidation_threshold; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.continuous_aggs_invalidation_threshold (hypertable_id, watermark) FROM stdin;
4	-210866803200000000
\.


--
-- Data for Name: continuous_aggs_materialization_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.continuous_aggs_materialization_invalidation_log (materialization_id, lowest_modified_value, greatest_modified_value) FROM stdin;
13	-9223372036854775808	9223372036854775807
14	-9223372036854775808	9223372036854775807
\.


--
-- Data for Name: continuous_aggs_materialization_ranges; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.continuous_aggs_materialization_ranges (materialization_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_watermark; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.continuous_aggs_watermark (mat_hypertable_id, watermark) FROM stdin;
13	-210866803200000000
14	-210866803200000000
\.


--
-- Data for Name: metadata; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.metadata (key, value, include_in_telemetry) FROM stdin;
install_timestamp	2025-12-08 22:21:34.415266+00	t
timescaledb_version	2.24.0	f
exported_uuid	fa7e98df-5d5c-4f08-bda1-f8a89cc06e6d	t
\.


--
-- Data for Name: tablespace; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: kapman
--

COPY _timescaledb_catalog.tablespace (id, hypertable_id, tablespace_name) FROM stdin;
\.


--
-- Data for Name: bgw_job; Type: TABLE DATA; Schema: _timescaledb_config; Owner: kapman
--

COPY _timescaledb_config.bgw_job (id, application_name, schedule_interval, max_runtime, max_retries, retry_period, proc_schema, proc_name, owner, scheduled, fixed_schedule, initial_start, hypertable_id, config, check_schema, check_name, timezone) FROM stdin;
1000	Columnstore Policy [1000]	12:00:00	00:00:00	-1	01:00:00	_timescaledb_functions	policy_compression	kapman	t	f	\N	4	{"hypertable_id": 4, "compress_after": "7 days"}	_timescaledb_functions	policy_compression_check	\N
1001	Columnstore Policy [1001]	12:00:00	00:00:00	-1	01:00:00	_timescaledb_functions	policy_compression	kapman	t	f	\N	5	{"hypertable_id": 5, "compress_after": "1 day"}	_timescaledb_functions	policy_compression_check	\N
1002	Columnstore Policy [1002]	12:00:00	00:00:00	-1	01:00:00	_timescaledb_functions	policy_compression	kapman	t	f	\N	6	{"hypertable_id": 6, "compress_after": "1 day"}	_timescaledb_functions	policy_compression_check	\N
1003	Retention Policy [1003]	1 day	00:05:00	-1	00:05:00	_timescaledb_functions	policy_retention	kapman	t	f	\N	4	{"drop_after": "1 year", "hypertable_id": 4}	_timescaledb_functions	policy_retention_check	\N
1004	Retention Policy [1004]	1 day	00:05:00	-1	00:05:00	_timescaledb_functions	policy_retention	kapman	t	f	\N	5	{"drop_after": "30 days", "hypertable_id": 5}	_timescaledb_functions	policy_retention_check	\N
1005	Retention Policy [1005]	1 day	00:05:00	-1	00:05:00	_timescaledb_functions	policy_retention	kapman	t	f	\N	6	{"drop_after": "90 days", "hypertable_id": 6}	_timescaledb_functions	policy_retention_check	\N
1006	Columnstore Policy [1006]	12:00:00	00:00:00	-1	01:00:00	_timescaledb_functions	policy_compression	kapman	t	f	\N	1	{"hypertable_id": 1, "compress_after": "1 year"}	_timescaledb_functions	policy_compression_check	\N
1007	Columnstore Policy [1007]	12:00:00	00:00:00	-1	01:00:00	_timescaledb_functions	policy_compression	kapman	t	f	\N	3	{"hypertable_id": 3, "compress_after": "1 year"}	_timescaledb_functions	policy_compression_check	\N
1008	Retention Policy [1008]	1 day	00:05:00	-1	00:05:00	_timescaledb_functions	policy_retention	kapman	t	f	\N	1	{"drop_after": "3 years", "hypertable_id": 1}	_timescaledb_functions	policy_retention_check	\N
1009	Retention Policy [1009]	1 day	00:05:00	-1	00:05:00	_timescaledb_functions	policy_retention	kapman	t	f	\N	2	{"drop_after": "90 days", "hypertable_id": 2}	_timescaledb_functions	policy_retention_check	\N
1010	Retention Policy [1010]	1 day	00:05:00	-1	00:05:00	_timescaledb_functions	policy_retention	kapman	t	f	\N	3	{"drop_after": "2 years", "hypertable_id": 3}	_timescaledb_functions	policy_retention_check	\N
\.


--
-- Data for Name: _compressed_hypertable_10; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: kapman
--

COPY _timescaledb_internal._compressed_hypertable_10  FROM stdin;
\.


--
-- Data for Name: _compressed_hypertable_11; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: kapman
--

COPY _timescaledb_internal._compressed_hypertable_11  FROM stdin;
\.


--
-- Data for Name: _compressed_hypertable_12; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: kapman
--

COPY _timescaledb_internal._compressed_hypertable_12  FROM stdin;
\.


--
-- Data for Name: _compressed_hypertable_7; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: kapman
--

COPY _timescaledb_internal._compressed_hypertable_7  FROM stdin;
\.


--
-- Data for Name: _compressed_hypertable_8; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: kapman
--

COPY _timescaledb_internal._compressed_hypertable_8  FROM stdin;
\.


--
-- Data for Name: _compressed_hypertable_9; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: kapman
--

COPY _timescaledb_internal._compressed_hypertable_9  FROM stdin;
\.


--
-- Data for Name: _hyper_1_1_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: kapman
--

COPY _timescaledb_internal._hyper_1_1_chunk ("time", symbol_id, open, high, low, close, volume, vwap, source) FROM stdin;
2024-12-06 05:00:00+00	e535378d-6ae5-54cb-aa4f-17b7b7894ac0	242.9050	244.6300	242.0800	242.8400	36870619	243.1833	polygon_s3
\.


--
-- Data for Name: _materialized_hypertable_13; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: kapman
--

COPY _timescaledb_internal._materialized_hypertable_13 (bucket, asset_id, open, high, low, close, volume, vwap, trade_count) FROM stdin;
\.


--
-- Data for Name: _materialized_hypertable_14; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: kapman
--

COPY _timescaledb_internal._materialized_hypertable_14 (bucket, asset_id, open, high, low, close, volume, vwap, trade_count) FROM stdin;
\.


--
-- Data for Name: accounts; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.accounts (id, user_id, name, broker_name, api_key, api_secret, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: assets; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.assets (id, symbol, name, exchange_id, type, is_active, min_price_increment, min_order_size, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: daily_snapshots; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.daily_snapshots ("time", symbol_id, wyckoff_phase, phase_confidence, phase_sub_stage, events_detected, primary_event, primary_event_confidence, bc_score, spring_score, composite_score, volatility_regime, checklist_json, technical_indicators, dealer_metrics, price_metrics, model_version, data_quality, created_at) FROM stdin;
\.


--
-- Data for Name: exchanges; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.exchanges (id, name, code, country, timezone, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: job_runs; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.job_runs (id, job_name, started_at, completed_at, status, tickers_processed, errors_json, duration_seconds, metadata) FROM stdin;
\.


--
-- Data for Name: market_data; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.market_data ("time", asset_id, open, high, low, close, volume, vwap, trade_count) FROM stdin;
\.


--
-- Data for Name: model_parameters; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.model_parameters (id, model_name, version, parameters_json, effective_from, effective_to, created_at, updated_at) FROM stdin;
1	wyckoff_v2	2.0.0	{"scoring": {"bc_signal_weights": [4, 4, 4, 4, 4, 4, 4], "spring_signal_weights": [3, 3, 3, 3]}, "event_detection": {"bc_volume_multiplier": 2.0, "sos_volume_multiplier": 1.5, "spring_recovery_threshold": 0.02}, "phase_thresholds": {"accumulation_min_score": 0.60, "distribution_min_score": 0.60}}	2025-12-08 22:21:34.743474+00	\N	2025-12-08 22:21:34.743474+00	2025-12-08 22:21:34.743474+00
\.


--
-- Data for Name: ohlcv_daily; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.ohlcv_daily ("time", symbol_id, open, high, low, close, volume, vwap, source) FROM stdin;
\.


--
-- Data for Name: options_chains; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.options_chains ("time", symbol_id, expiration_date, strike_price, option_type, bid, ask, last, volume, open_interest, implied_volatility, delta, gamma, theta, vega) FROM stdin;
\.


--
-- Data for Name: order_book_snapshots; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.order_book_snapshots ("time", asset_id, bid_price_1, bid_size_1, ask_price_1, ask_size_1) FROM stdin;
\.


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.orders (id, account_id, portfolio_id, asset_id, client_order_id, exchange_order_id, type, side, quantity, price, stop_price, time_in_force, status, filled_quantity, average_fill_price, commission, created_at, updated_at, filled_at, cancelled_at, notes) FROM stdin;
\.


--
-- Data for Name: portfolio_tickers; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.portfolio_tickers (portfolio_id, ticker_id, priority, added_at) FROM stdin;
00000000-0000-0000-0000-000000000001	e535378d-6ae5-54cb-aa4f-17b7b7894ac0	P0	2025-12-08 22:21:34.725298+00
00000000-0000-0000-0000-000000000001	ccf8421d-bd0d-570f-ab70-3ca0bf7a825e	P0	2025-12-08 22:21:34.725298+00
00000000-0000-0000-0000-000000000001	65be27b1-5cfd-5140-ac51-22456ff7f5a3	P1	2025-12-08 22:21:34.725298+00
00000000-0000-0000-0000-000000000001	1f6d5e68-bf90-5941-98e4-17bd256ea134	P1	2025-12-08 22:21:34.725298+00
00000000-0000-0000-0000-000000000001	8f36ad84-5639-568e-b1fc-461afb4c2792	P1	2025-12-08 22:21:34.725298+00
00000000-0000-0000-0000-000000000001	ad7f9b62-405b-56a1-af1f-5bf7975a0c1f	P1	2025-12-08 22:21:34.725298+00
00000000-0000-0000-0000-000000000001	e5b5804d-3350-574a-b1db-a14c4e0cf470	P1	2025-12-08 22:21:34.725298+00
\.


--
-- Data for Name: portfolios; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.portfolios (id, name, description, created_at, updated_at) FROM stdin;
00000000-0000-0000-0000-000000000001	Kapman Core	Primary trading portfolio	2025-12-08 22:21:34.718562+00	2025-12-08 22:21:34.718562+00
\.


--
-- Data for Name: positions; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.positions (id, account_id, portfolio_id, asset_id, quantity, side, average_entry_price, current_price, unrealized_pnl, realized_pnl, is_open, opened_at, closed_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: recommendation_outcomes; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.recommendation_outcomes (id, recommendation_id, evaluation_date, evaluation_window_days, entry_price_actual, exit_price_actual, high_price_during_window, low_price_during_window, days_to_target, days_to_stop, days_held, max_favorable_excursion, max_adverse_excursion, direction_correct, predicted_confidence, directional_brier, actual_return_pct, hit_profit_target, hit_stop_loss, success_score_v1, outcome_status, notes, evaluated_at) FROM stdin;
\.


--
-- Data for Name: recommendations; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.recommendations (id, snapshot_time, symbol_id, recommendation_date, direction, action, confidence, justification, entry_price_target, stop_loss, profit_target, risk_reward_ratio, option_strike, option_expiration, option_type, option_strategy, status, model_version, created_at) FROM stdin;
\.


--
-- Data for Name: signals; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.signals (id, strategy_id, asset_id, type, strength, price_target, stop_loss, notes, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: strategies; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.strategies (id, user_id, name, type, description, parameters, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: tickers; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.tickers (id, symbol, name, sector, is_active, created_at, updated_at) FROM stdin;
e535378d-6ae5-54cb-aa4f-17b7b7894ac0	AAPL	Apple Inc.	Technology	t	2025-12-08 22:21:34.724063+00	2025-12-08 22:21:34.724063+00
ccf8421d-bd0d-570f-ab70-3ca0bf7a825e	MSFT	Microsoft Corporation	Technology	t	2025-12-08 22:21:34.724063+00	2025-12-08 22:21:34.724063+00
65be27b1-5cfd-5140-ac51-22456ff7f5a3	GOOGL	Alphabet Inc.	Communication Services	t	2025-12-08 22:21:34.724063+00	2025-12-08 22:21:34.724063+00
1f6d5e68-bf90-5941-98e4-17bd256ea134	AMZN	Amazon.com Inc.	Consumer Cyclical	t	2025-12-08 22:21:34.724063+00	2025-12-08 22:21:34.724063+00
8f36ad84-5639-568e-b1fc-461afb4c2792	META	Meta Platforms Inc.	Communication Services	t	2025-12-08 22:21:34.724063+00	2025-12-08 22:21:34.724063+00
ad7f9b62-405b-56a1-af1f-5bf7975a0c1f	TSLA	Tesla Inc.	Consumer Cyclical	t	2025-12-08 22:21:34.724063+00	2025-12-08 22:21:34.724063+00
e5b5804d-3350-574a-b1db-a14c4e0cf470	NVDA	NVIDIA Corporation	Technology	t	2025-12-08 22:21:34.724063+00	2025-12-08 22:21:34.724063+00
\.


--
-- Data for Name: trade_history; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.trade_history ("time", asset_id, price, quantity, side, is_buyer_maker, trade_id) FROM stdin;
\.


--
-- Data for Name: trades; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.trades (id, account_id, portfolio_id, asset_id, quantity, price, side, fee, fee_asset, realized_pnl, strategy_id, signal_id, notes, created_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: kapman
--

COPY public.users (id, email, hashed_password, first_name, last_name, is_active, is_verified, last_login, created_at, updated_at) FROM stdin;
\.


--
-- Name: chunk_column_stats_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: kapman
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_column_stats_id_seq', 1, false);


--
-- Name: chunk_constraint_name; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: kapman
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_constraint_name', 2, true);


--
-- Name: chunk_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: kapman
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_id_seq', 1, true);


--
-- Name: continuous_agg_migrate_plan_step_step_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: kapman
--

SELECT pg_catalog.setval('_timescaledb_catalog.continuous_agg_migrate_plan_step_step_id_seq', 1, false);


--
-- Name: dimension_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: kapman
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_id_seq', 8, true);


--
-- Name: dimension_slice_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: kapman
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_slice_id_seq', 1, true);


--
-- Name: hypertable_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: kapman
--

SELECT pg_catalog.setval('_timescaledb_catalog.hypertable_id_seq', 14, true);


--
-- Name: bgw_job_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_config; Owner: kapman
--

SELECT pg_catalog.setval('_timescaledb_config.bgw_job_id_seq', 1010, true);


--
-- Name: model_parameters_id_seq; Type: SEQUENCE SET; Schema: public; Owner: kapman
--

SELECT pg_catalog.setval('public.model_parameters_id_seq', 1, true);


--
-- Name: _hyper_1_1_chunk 1_1_ohlcv_daily_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: kapman
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk
    ADD CONSTRAINT "1_1_ohlcv_daily_pkey" PRIMARY KEY ("time", symbol_id);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: accounts accounts_user_id_name_key; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_name_key UNIQUE (user_id, name);


--
-- Name: assets assets_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (id);


--
-- Name: assets assets_symbol_exchange_id_key; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_symbol_exchange_id_key UNIQUE (symbol, exchange_id);


--
-- Name: daily_snapshots daily_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.daily_snapshots
    ADD CONSTRAINT daily_snapshots_pkey PRIMARY KEY ("time", symbol_id);


--
-- Name: exchanges exchanges_code_key; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_code_key UNIQUE (code);


--
-- Name: exchanges exchanges_name_key; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_name_key UNIQUE (name);


--
-- Name: exchanges exchanges_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_pkey PRIMARY KEY (id);


--
-- Name: job_runs job_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.job_runs
    ADD CONSTRAINT job_runs_pkey PRIMARY KEY (id);


--
-- Name: market_data market_data_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.market_data
    ADD CONSTRAINT market_data_pkey PRIMARY KEY ("time", asset_id);


--
-- Name: model_parameters model_parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.model_parameters
    ADD CONSTRAINT model_parameters_pkey PRIMARY KEY (id);


--
-- Name: ohlcv_daily ohlcv_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.ohlcv_daily
    ADD CONSTRAINT ohlcv_daily_pkey PRIMARY KEY ("time", symbol_id);


--
-- Name: options_chains options_chains_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.options_chains
    ADD CONSTRAINT options_chains_pkey PRIMARY KEY ("time", symbol_id, expiration_date, strike_price, option_type);


--
-- Name: order_book_snapshots order_book_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.order_book_snapshots
    ADD CONSTRAINT order_book_snapshots_pkey PRIMARY KEY ("time", asset_id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: portfolio_tickers portfolio_tickers_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.portfolio_tickers
    ADD CONSTRAINT portfolio_tickers_pkey PRIMARY KEY (portfolio_id, ticker_id);


--
-- Name: portfolios portfolios_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.portfolios
    ADD CONSTRAINT portfolios_pkey PRIMARY KEY (id);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: recommendation_outcomes recommendation_outcomes_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.recommendation_outcomes
    ADD CONSTRAINT recommendation_outcomes_pkey PRIMARY KEY (id);


--
-- Name: recommendations recommendations_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT recommendations_pkey PRIMARY KEY (id);


--
-- Name: signals signals_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_pkey PRIMARY KEY (id);


--
-- Name: strategies strategies_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.strategies
    ADD CONSTRAINT strategies_pkey PRIMARY KEY (id);


--
-- Name: strategies strategies_user_id_name_key; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.strategies
    ADD CONSTRAINT strategies_user_id_name_key UNIQUE (user_id, name);


--
-- Name: tickers tickers_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.tickers
    ADD CONSTRAINT tickers_pkey PRIMARY KEY (id);


--
-- Name: tickers tickers_symbol_key; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.tickers
    ADD CONSTRAINT tickers_symbol_key UNIQUE (symbol);


--
-- Name: trade_history trade_history_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.trade_history
    ADD CONSTRAINT trade_history_pkey PRIMARY KEY ("time", asset_id, trade_id);


--
-- Name: trades trades_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_pkey PRIMARY KEY (id);


--
-- Name: model_parameters unique_model_version; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.model_parameters
    ADD CONSTRAINT unique_model_version UNIQUE (model_name, version);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: _hyper_1_1_chunk_idx_ohlcv_daily_symbol; Type: INDEX; Schema: _timescaledb_internal; Owner: kapman
--

CREATE INDEX _hyper_1_1_chunk_idx_ohlcv_daily_symbol ON _timescaledb_internal._hyper_1_1_chunk USING btree (symbol_id, "time" DESC);


--
-- Name: _hyper_1_1_chunk_ohlcv_daily_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: kapman
--

CREATE INDEX _hyper_1_1_chunk_ohlcv_daily_time_idx ON _timescaledb_internal._hyper_1_1_chunk USING btree ("time" DESC);


--
-- Name: _materialized_hypertable_13_asset_id_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: kapman
--

CREATE INDEX _materialized_hypertable_13_asset_id_bucket_idx ON _timescaledb_internal._materialized_hypertable_13 USING btree (asset_id, bucket DESC);


--
-- Name: _materialized_hypertable_13_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: kapman
--

CREATE INDEX _materialized_hypertable_13_bucket_idx ON _timescaledb_internal._materialized_hypertable_13 USING btree (bucket DESC);


--
-- Name: _materialized_hypertable_14_asset_id_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: kapman
--

CREATE INDEX _materialized_hypertable_14_asset_id_bucket_idx ON _timescaledb_internal._materialized_hypertable_14 USING btree (asset_id, bucket DESC);


--
-- Name: _materialized_hypertable_14_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: kapman
--

CREATE INDEX _materialized_hypertable_14_bucket_idx ON _timescaledb_internal._materialized_hypertable_14 USING btree (bucket DESC);


--
-- Name: daily_snapshots_time_idx; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX daily_snapshots_time_idx ON public.daily_snapshots USING btree ("time" DESC);


--
-- Name: idx_daily_snapshots_symbol; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_daily_snapshots_symbol ON public.daily_snapshots USING btree (symbol_id, "time" DESC);


--
-- Name: idx_job_runs_job_name; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_job_runs_job_name ON public.job_runs USING btree (job_name);


--
-- Name: idx_job_runs_started_at; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_job_runs_started_at ON public.job_runs USING btree (started_at DESC);


--
-- Name: idx_job_runs_status; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_job_runs_status ON public.job_runs USING btree (status);


--
-- Name: idx_ohlcv_daily_symbol; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_ohlcv_daily_symbol ON public.ohlcv_daily USING btree (symbol_id, "time" DESC);


--
-- Name: idx_options_chains_symbol; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_options_chains_symbol ON public.options_chains USING btree (symbol_id, "time" DESC);


--
-- Name: idx_orders_asset_id; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_orders_asset_id ON public.orders USING btree (asset_id);


--
-- Name: idx_orders_created_at; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_orders_created_at ON public.orders USING btree (created_at);


--
-- Name: idx_orders_portfolio_id; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_orders_portfolio_id ON public.orders USING btree (portfolio_id);


--
-- Name: idx_outcomes_date; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_outcomes_date ON public.recommendation_outcomes USING btree (evaluation_date DESC);


--
-- Name: idx_outcomes_recommendation; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_outcomes_recommendation ON public.recommendation_outcomes USING btree (recommendation_id);


--
-- Name: idx_positions_asset_id; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_positions_asset_id ON public.positions USING btree (asset_id);


--
-- Name: idx_positions_portfolio_id; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_positions_portfolio_id ON public.positions USING btree (portfolio_id);


--
-- Name: idx_recommendations_status; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_recommendations_status ON public.recommendations USING btree (status, recommendation_date DESC);


--
-- Name: idx_recommendations_symbol; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_recommendations_symbol ON public.recommendations USING btree (symbol_id, recommendation_date DESC);


--
-- Name: idx_signals_asset_id; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_signals_asset_id ON public.signals USING btree (asset_id);


--
-- Name: idx_signals_strategy_id; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_signals_strategy_id ON public.signals USING btree (strategy_id);


--
-- Name: idx_trades_asset_id; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_trades_asset_id ON public.trades USING btree (asset_id);


--
-- Name: idx_trades_created_at; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_trades_created_at ON public.trades USING btree (created_at);


--
-- Name: idx_trades_portfolio_id; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX idx_trades_portfolio_id ON public.trades USING btree (portfolio_id);


--
-- Name: market_data_time_idx; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX market_data_time_idx ON public.market_data USING btree ("time" DESC);


--
-- Name: ohlcv_daily_time_idx; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX ohlcv_daily_time_idx ON public.ohlcv_daily USING btree ("time" DESC);


--
-- Name: options_chains_time_idx; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX options_chains_time_idx ON public.options_chains USING btree ("time" DESC);


--
-- Name: order_book_snapshots_time_idx; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX order_book_snapshots_time_idx ON public.order_book_snapshots USING btree ("time" DESC);


--
-- Name: trade_history_time_idx; Type: INDEX; Schema: public; Owner: kapman
--

CREATE INDEX trade_history_time_idx ON public.trade_history USING btree ("time" DESC);


--
-- Name: accounts update_accounts_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_accounts_modtime BEFORE UPDATE ON public.accounts FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: assets update_assets_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_assets_modtime BEFORE UPDATE ON public.assets FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: exchanges update_exchanges_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_exchanges_modtime BEFORE UPDATE ON public.exchanges FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: model_parameters update_model_parameters_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_model_parameters_modtime BEFORE UPDATE ON public.model_parameters FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: orders update_orders_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_orders_modtime BEFORE UPDATE ON public.orders FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: portfolios update_portfolios_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_portfolios_modtime BEFORE UPDATE ON public.portfolios FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: positions update_positions_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_positions_modtime BEFORE UPDATE ON public.positions FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: signals update_signals_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_signals_modtime BEFORE UPDATE ON public.signals FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: strategies update_strategies_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_strategies_modtime BEFORE UPDATE ON public.strategies FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: tickers update_tickers_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_tickers_modtime BEFORE UPDATE ON public.tickers FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: users update_users_modtime; Type: TRIGGER; Schema: public; Owner: kapman
--

CREATE TRIGGER update_users_modtime BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: _hyper_1_1_chunk 1_2_ohlcv_daily_symbol_id_fkey; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: kapman
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk
    ADD CONSTRAINT "1_2_ohlcv_daily_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.tickers(id);


--
-- Name: accounts accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: assets assets_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_exchange_id_fkey FOREIGN KEY (exchange_id) REFERENCES public.exchanges(id);


--
-- Name: daily_snapshots daily_snapshots_symbol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.daily_snapshots
    ADD CONSTRAINT daily_snapshots_symbol_id_fkey FOREIGN KEY (symbol_id) REFERENCES public.tickers(id);


--
-- Name: market_data market_data_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.market_data
    ADD CONSTRAINT market_data_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: ohlcv_daily ohlcv_daily_symbol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.ohlcv_daily
    ADD CONSTRAINT ohlcv_daily_symbol_id_fkey FOREIGN KEY (symbol_id) REFERENCES public.tickers(id);


--
-- Name: options_chains options_chains_symbol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.options_chains
    ADD CONSTRAINT options_chains_symbol_id_fkey FOREIGN KEY (symbol_id) REFERENCES public.tickers(id);


--
-- Name: order_book_snapshots order_book_snapshots_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.order_book_snapshots
    ADD CONSTRAINT order_book_snapshots_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: orders orders_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: orders orders_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: orders orders_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES public.portfolios(id) ON DELETE CASCADE;


--
-- Name: portfolio_tickers portfolio_tickers_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.portfolio_tickers
    ADD CONSTRAINT portfolio_tickers_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES public.portfolios(id) ON DELETE CASCADE;


--
-- Name: portfolio_tickers portfolio_tickers_ticker_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.portfolio_tickers
    ADD CONSTRAINT portfolio_tickers_ticker_id_fkey FOREIGN KEY (ticker_id) REFERENCES public.tickers(id) ON DELETE CASCADE;


--
-- Name: positions positions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: positions positions_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: positions positions_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES public.portfolios(id) ON DELETE CASCADE;


--
-- Name: recommendation_outcomes recommendation_outcomes_recommendation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.recommendation_outcomes
    ADD CONSTRAINT recommendation_outcomes_recommendation_id_fkey FOREIGN KEY (recommendation_id) REFERENCES public.recommendations(id) ON DELETE CASCADE;


--
-- Name: recommendations recommendations_snapshot_time_symbol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT recommendations_snapshot_time_symbol_id_fkey FOREIGN KEY (snapshot_time, symbol_id) REFERENCES public.daily_snapshots("time", symbol_id);


--
-- Name: recommendations recommendations_symbol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT recommendations_symbol_id_fkey FOREIGN KEY (symbol_id) REFERENCES public.tickers(id);


--
-- Name: signals signals_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: signals signals_strategy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_strategy_id_fkey FOREIGN KEY (strategy_id) REFERENCES public.strategies(id) ON DELETE CASCADE;


--
-- Name: strategies strategies_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.strategies
    ADD CONSTRAINT strategies_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: trade_history trade_history_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.trade_history
    ADD CONSTRAINT trade_history_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: trades trades_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: trades trades_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: trades trades_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: kapman
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES public.portfolios(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

