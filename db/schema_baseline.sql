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
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: asset_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.asset_type AS ENUM (
    'STOCK',
    'OPTION',
    'CRYPTO',
    'FUTURE'
);


--
-- Name: option_strategy; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.option_strategy AS ENUM (
    'LONG_CALL',
    'LONG_PUT',
    'CSP',
    'VERTICAL_SPREAD'
);


--
-- Name: option_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.option_type AS ENUM (
    'C',
    'P'
);


--
-- Name: order_side; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.order_side AS ENUM (
    'BUY',
    'SELL'
);


--
-- Name: order_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.order_status AS ENUM (
    'OPEN',
    'FILLED',
    'PARTIALLY_FILLED',
    'CANCELLED',
    'REJECTED'
);


--
-- Name: order_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.order_type AS ENUM (
    'MARKET',
    'LIMIT',
    'STOP',
    'STOP_LIMIT',
    'TRAILING_STOP'
);


--
-- Name: outcome_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.outcome_status AS ENUM (
    'WIN',
    'LOSS',
    'NEUTRAL'
);


--
-- Name: position_side; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.position_side AS ENUM (
    'LONG',
    'SHORT'
);


--
-- Name: recommendation_action; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.recommendation_action AS ENUM (
    'BUY',
    'SELL',
    'HOLD',
    'HEDGE'
);


--
-- Name: recommendation_direction; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.recommendation_direction AS ENUM (
    'LONG',
    'SHORT',
    'NEUTRAL'
);


--
-- Name: recommendation_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.recommendation_status AS ENUM (
    'active',
    'closed',
    'expired'
);


--
-- Name: signal_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.signal_type AS ENUM (
    'ENTRY',
    'EXIT',
    'STOP_LOSS',
    'TAKE_PROFIT'
);


--
-- Name: strategy_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.strategy_type AS ENUM (
    'MOMENTUM',
    'MEAN_REVERSION',
    'ARBITRAGE',
    'MARKET_MAKING',
    'HEDGING'
);


--
-- Name: fn_symbols_needing_ohlcv(date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_symbols_needing_ohlcv(target_date date DEFAULT (CURRENT_DATE - 1)) RETURNS TABLE(symbol character varying, ticker_id uuid, last_date date, days_behind integer)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.symbol,
        t.id as ticker_id,
        t.last_ohlcv_date,
        (target_date - COALESCE(t.last_ohlcv_date, '2020-01-01'::DATE))::INTEGER as days_behind
    FROM tickers t
    WHERE t.is_active = true
        AND (t.last_ohlcv_date IS NULL OR t.last_ohlcv_date < target_date)
    ORDER BY days_behind DESC;
END;
$$;


--
-- Name: fn_watchlist_needing_analysis(date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_watchlist_needing_analysis(target_date date DEFAULT (CURRENT_DATE - 1)) RETURNS TABLE(symbol character varying, ticker_id uuid, priority integer, last_analysis date, has_ohlcv boolean)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.symbol,
        t.id as ticker_id,
        MIN(pt.priority) as priority,
        t.last_analysis_date,
        (t.last_ohlcv_date >= target_date) as has_ohlcv
    FROM tickers t
    JOIN portfolio_tickers pt ON t.id = pt.ticker_id
    WHERE t.is_active = true
        AND (t.last_analysis_date IS NULL OR t.last_analysis_date < target_date)
        AND t.last_ohlcv_date >= target_date  -- Only if OHLCV is fresh
    GROUP BY t.id, t.symbol, t.last_analysis_date, t.last_ohlcv_date
    ORDER BY priority, symbol;
END;
$$;


--
-- Name: update_modified_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_modified_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _compressed_hypertable_10; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_10 (
);


--
-- Name: _compressed_hypertable_11; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_11 (
);


--
-- Name: _compressed_hypertable_12; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_12 (
);


--
-- Name: _compressed_hypertable_7; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_7 (
);


--
-- Name: _compressed_hypertable_8; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_8 (
);


--
-- Name: _compressed_hypertable_9; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_9 (
);


--
-- Name: market_data; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: _direct_view_13; Type: VIEW; Schema: _timescaledb_internal; Owner: -
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


--
-- Name: _direct_view_14; Type: VIEW; Schema: _timescaledb_internal; Owner: -
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


--
-- Name: ohlcv_daily; Type: TABLE; Schema: public; Owner: -
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
    source character varying(50) DEFAULT 'polygon_s3'::character varying,
    ticker_id uuid,
    is_adjusted boolean DEFAULT true
);


--
-- Name: COLUMN ohlcv_daily.ticker_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ohlcv_daily.ticker_id IS 'Optional FK to tickers table for joins';


--
-- Name: COLUMN ohlcv_daily.is_adjusted; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ohlcv_daily.is_adjusted IS 'Whether prices are split/dividend adjusted';


--
-- Name: _hyper_1_1_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_1_chunk (
    CONSTRAINT constraint_1 CHECK ((("time" >= '2024-12-05 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-12-12 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_daily);


--
-- Name: _materialized_hypertable_13; Type: TABLE; Schema: _timescaledb_internal; Owner: -
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


--
-- Name: _materialized_hypertable_14; Type: TABLE; Schema: _timescaledb_internal; Owner: -
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


--
-- Name: _partial_view_13; Type: VIEW; Schema: _timescaledb_internal; Owner: -
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


--
-- Name: _partial_view_14; Type: VIEW; Schema: _timescaledb_internal; Owner: -
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


--
-- Name: compress_hyper_10_2_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal.compress_hyper_10_2_chunk (
    _ts_meta_count integer,
    symbol_id uuid,
    _ts_meta_min_1 timestamp with time zone,
    _ts_meta_max_1 timestamp with time zone,
    "time" _timescaledb_internal.compressed_data,
    open _timescaledb_internal.compressed_data,
    high _timescaledb_internal.compressed_data,
    low _timescaledb_internal.compressed_data,
    close _timescaledb_internal.compressed_data,
    volume _timescaledb_internal.compressed_data,
    vwap _timescaledb_internal.compressed_data,
    source _timescaledb_internal.compressed_data,
    _ts_meta_min_2 uuid,
    _ts_meta_max_2 uuid,
    ticker_id _timescaledb_internal.compressed_data,
    is_adjusted _timescaledb_internal.compressed_data
)
WITH (toast_tuple_target='128');
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN _ts_meta_count SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN symbol_id SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN _ts_meta_min_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN _ts_meta_max_1 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN "time" SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN open SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN open SET STORAGE EXTENDED;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN high SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN high SET STORAGE EXTENDED;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN low SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN low SET STORAGE EXTENDED;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN close SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN close SET STORAGE EXTENDED;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN volume SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN vwap SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN vwap SET STORAGE EXTENDED;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN source SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN source SET STORAGE EXTENDED;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN _ts_meta_min_2 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN _ts_meta_max_2 SET STATISTICS 1000;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN ticker_id SET STATISTICS 0;
ALTER TABLE ONLY _timescaledb_internal.compress_hyper_10_2_chunk ALTER COLUMN is_adjusted SET STATISTICS 0;


--
-- Name: accounts; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: assets; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: connection_test; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.connection_test (
    id integer NOT NULL,
    test_time timestamp without time zone NOT NULL,
    status text NOT NULL
);


--
-- Name: connection_test_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.connection_test_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: connection_test_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.connection_test_id_seq OWNED BY public.connection_test.id;


--
-- Name: daily_snapshots; Type: TABLE; Schema: public; Owner: -
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
    rsi_14 numeric(6,2),
    macd_line numeric(12,4),
    macd_signal numeric(12,4),
    macd_histogram numeric(12,4),
    stoch_k numeric(6,2),
    stoch_d numeric(6,2),
    mfi_14 numeric(6,2),
    sma_20 numeric(12,4),
    sma_50 numeric(12,4),
    sma_200 numeric(12,4),
    ema_12 numeric(12,4),
    ema_26 numeric(12,4),
    adx_14 numeric(6,2),
    atr_14 numeric(12,4),
    bbands_upper numeric(12,4),
    bbands_middle numeric(12,4),
    bbands_lower numeric(12,4),
    bbands_width numeric(8,4),
    obv bigint,
    vwap numeric(12,4),
    gex_total numeric(18,2),
    gex_net numeric(18,2),
    gamma_flip_level numeric(12,4),
    call_wall_primary numeric(12,2),
    call_wall_primary_oi integer,
    put_wall_primary numeric(12,2),
    put_wall_primary_oi integer,
    dgpi numeric(5,2),
    dealer_position character varying(15),
    iv_skew_25d numeric(6,4),
    iv_term_structure numeric(6,4),
    put_call_ratio_oi numeric(6,4),
    put_call_ratio_volume numeric(6,4),
    average_iv numeric(6,4),
    iv_rank numeric(5,2),
    iv_percentile numeric(5,2),
    volatility_metrics_json jsonb,
    rvol numeric(8,4),
    vsi numeric(8,4),
    hv_20 numeric(6,4),
    hv_60 numeric(6,4),
    iv_hv_diff numeric(6,4),
    price_vs_sma20 numeric(6,4),
    price_vs_sma50 numeric(6,4),
    price_vs_sma200 numeric(6,4),
    events_json jsonb,
    CONSTRAINT chk_dealer_position CHECK (((dealer_position IS NULL) OR ((dealer_position)::text = ANY ((ARRAY['long_gamma'::character varying, 'short_gamma'::character varying, 'neutral'::character varying])::text[])))),
    CONSTRAINT chk_dgpi_range CHECK (((dgpi IS NULL) OR ((dgpi >= ('-100'::integer)::numeric) AND (dgpi <= (100)::numeric)))),
    CONSTRAINT daily_snapshots_bc_score_check CHECK (((bc_score >= 0) AND (bc_score <= 28))),
    CONSTRAINT daily_snapshots_phase_confidence_check CHECK (((phase_confidence >= (0)::numeric) AND (phase_confidence <= (1)::numeric))),
    CONSTRAINT daily_snapshots_spring_score_check CHECK (((spring_score >= 0) AND (spring_score <= 12))),
    CONSTRAINT daily_snapshots_wyckoff_phase_check CHECK (((wyckoff_phase)::text = ANY ((ARRAY['A'::character varying, 'B'::character varying, 'C'::character varying, 'D'::character varying, 'E'::character varying])::text[])))
);


--
-- Name: COLUMN daily_snapshots.rsi_14; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.rsi_14 IS '14-period RSI (0-100)';


--
-- Name: COLUMN daily_snapshots.macd_histogram; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.macd_histogram IS 'MACD histogram (MACD line - signal)';


--
-- Name: COLUMN daily_snapshots.adx_14; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.adx_14 IS '14-period ADX trend strength (0-100)';


--
-- Name: COLUMN daily_snapshots.bbands_width; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.bbands_width IS 'Bollinger Band width as percentage';


--
-- Name: COLUMN daily_snapshots.gex_total; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.gex_total IS 'Total Gamma Exposure across all strikes';


--
-- Name: COLUMN daily_snapshots.gex_net; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.gex_net IS 'Net directional Gamma Exposure';


--
-- Name: COLUMN daily_snapshots.gamma_flip_level; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.gamma_flip_level IS 'Price level where dealers flip long/short gamma';


--
-- Name: COLUMN daily_snapshots.call_wall_primary; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.call_wall_primary IS 'Highest OI call strike (resistance)';


--
-- Name: COLUMN daily_snapshots.put_wall_primary; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.put_wall_primary IS 'Highest OI put strike (support)';


--
-- Name: COLUMN daily_snapshots.dgpi; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.dgpi IS 'Dealer Gamma Pressure Index (-100 to +100)';


--
-- Name: COLUMN daily_snapshots.dealer_position; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.dealer_position IS 'Current dealer gamma positioning';


--
-- Name: COLUMN daily_snapshots.iv_skew_25d; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.iv_skew_25d IS '25-delta put-call IV spread (positive = put premium)';


--
-- Name: COLUMN daily_snapshots.iv_term_structure; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.iv_term_structure IS 'Long vs short-dated IV difference (negative = backwardation)';


--
-- Name: COLUMN daily_snapshots.put_call_ratio_oi; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.put_call_ratio_oi IS 'Put/Call ratio based on open interest';


--
-- Name: COLUMN daily_snapshots.put_call_ratio_volume; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.put_call_ratio_volume IS 'Put/Call ratio based on volume';


--
-- Name: COLUMN daily_snapshots.average_iv; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.average_iv IS 'OI-weighted average implied volatility';


--
-- Name: COLUMN daily_snapshots.iv_rank; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.iv_rank IS 'Current IV rank vs 52-week range (0-100)';


--
-- Name: COLUMN daily_snapshots.iv_percentile; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.iv_percentile IS 'Current IV percentile vs 52-week (0-100)';


--
-- Name: COLUMN daily_snapshots.rvol; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.rvol IS 'Relative Volume (1.0 = average, >1.5 = elevated)';


--
-- Name: COLUMN daily_snapshots.vsi; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.vsi IS 'Volume Surge Index (z-score, >2 = significant)';


--
-- Name: COLUMN daily_snapshots.hv_20; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.hv_20 IS '20-day Historical Volatility (annualized)';


--
-- Name: COLUMN daily_snapshots.hv_60; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.hv_60 IS '60-day Historical Volatility (annualized)';


--
-- Name: COLUMN daily_snapshots.iv_hv_diff; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.iv_hv_diff IS 'IV minus HV spread (positive = IV rich)';


--
-- Name: COLUMN daily_snapshots.price_vs_sma20; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.price_vs_sma20 IS 'Price distance from SMA20 as percentage';


--
-- Name: COLUMN daily_snapshots.price_vs_sma50; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.price_vs_sma50 IS 'Price distance from SMA50 as percentage';


--
-- Name: COLUMN daily_snapshots.price_vs_sma200; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.price_vs_sma200 IS 'Price distance from SMA200 as percentage';


--
-- Name: COLUMN daily_snapshots.events_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.daily_snapshots.events_json IS 'JSON array of Wyckoff events detected on this date. Each event contains: event_type, confidence, price_level, volume_context';


--
-- Name: exchanges; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: job_runs; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: market_data_daily; Type: VIEW; Schema: public; Owner: -
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


--
-- Name: market_data_hourly; Type: VIEW; Schema: public; Owner: -
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


--
-- Name: model_parameters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_parameters (
    id integer NOT NULL,
    model_name character varying(100) NOT NULL,
    version character varying(50) NOT NULL,
    parameters_json jsonb NOT NULL,
    effective_from timestamp with time zone DEFAULT now() NOT NULL,
    effective_to timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    notes text
);


--
-- Name: COLUMN model_parameters.notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.model_parameters.notes IS 'Free-form notes about parameter configuration, rationale, or observations';


--
-- Name: model_parameters_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: model_parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_parameters_id_seq OWNED BY public.model_parameters.id;


--
-- Name: ohlcv; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ohlcv (
    ticker_id uuid NOT NULL,
    date date NOT NULL,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    volume bigint,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: options_chains; Type: TABLE; Schema: public; Owner: -
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
    vega numeric(10,6),
    oi_change integer,
    volume_oi_ratio numeric(8,4),
    moneyness character varying(10),
    CONSTRAINT chk_moneyness CHECK (((moneyness IS NULL) OR ((moneyness)::text = ANY ((ARRAY['ITM'::character varying, 'ATM'::character varying, 'OTM'::character varying, 'DITM'::character varying, 'DOTM'::character varying])::text[]))))
);


--
-- Name: COLUMN options_chains.oi_change; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.options_chains.oi_change IS 'Change in OI from previous day';


--
-- Name: COLUMN options_chains.volume_oi_ratio; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.options_chains.volume_oi_ratio IS 'Volume / Open Interest ratio';


--
-- Name: COLUMN options_chains.moneyness; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.options_chains.moneyness IS 'ITM/ATM/OTM classification';


--
-- Name: options_daily_summary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.options_daily_summary (
    "time" timestamp with time zone NOT NULL,
    symbol_id uuid NOT NULL,
    total_call_oi integer,
    total_put_oi integer,
    total_oi integer GENERATED ALWAYS AS ((COALESCE(total_call_oi, 0) + COALESCE(total_put_oi, 0))) STORED,
    total_call_volume integer,
    total_put_volume integer,
    total_volume integer GENERATED ALWAYS AS ((COALESCE(total_call_volume, 0) + COALESCE(total_put_volume, 0))) STORED,
    put_call_oi_ratio numeric(6,4),
    put_call_volume_ratio numeric(6,4),
    weighted_avg_iv numeric(6,4),
    top_call_strike_1 numeric(12,2),
    top_call_oi_1 integer,
    top_call_strike_2 numeric(12,2),
    top_call_oi_2 integer,
    top_call_strike_3 numeric(12,2),
    top_call_oi_3 integer,
    top_put_strike_1 numeric(12,2),
    top_put_oi_1 integer,
    top_put_strike_2 numeric(12,2),
    top_put_oi_2 integer,
    top_put_strike_3 numeric(12,2),
    top_put_oi_3 integer,
    total_call_gamma numeric(18,8),
    total_put_gamma numeric(18,8),
    total_call_delta numeric(18,8),
    total_put_delta numeric(18,8),
    calculated_gex numeric(18,2),
    calculated_net_gex numeric(18,2),
    nearest_expiry date,
    expirations_count integer,
    contracts_analyzed integer,
    data_completeness numeric(4,3),
    source character varying(50) DEFAULT 'polygon_api'::character varying,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE options_daily_summary; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.options_daily_summary IS 'Daily aggregated options metrics per symbol for dealer analysis';


--
-- Name: COLUMN options_daily_summary.top_call_strike_1; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.options_daily_summary.top_call_strike_1 IS 'Highest OI call strike - primary resistance';


--
-- Name: COLUMN options_daily_summary.top_put_strike_1; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.options_daily_summary.top_put_strike_1 IS 'Highest OI put strike - primary support';


--
-- Name: COLUMN options_daily_summary.calculated_gex; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.options_daily_summary.calculated_gex IS 'Gamma Exposure calculated from Greeks + OI';


--
-- Name: order_book_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.order_book_snapshots (
    "time" timestamp with time zone NOT NULL,
    asset_id uuid NOT NULL,
    bid_price_1 numeric(20,8),
    bid_size_1 numeric(20,8),
    ask_price_1 numeric(20,8),
    ask_size_1 numeric(20,8)
);


--
-- Name: orders; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: portfolio_tickers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.portfolio_tickers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    portfolio_id uuid NOT NULL,
    ticker_id uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: portfolios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.portfolios (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: positions; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: recommendation_outcomes; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: recommendations; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: signals; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: strategies; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: tickers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tickers (
    symbol text NOT NULL,
    name text,
    exchange text,
    asset_type text,
    currency text,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid()
);


--
-- Name: trade_history; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: trades; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: _hyper_1_1_chunk source; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk ALTER COLUMN source SET DEFAULT 'polygon_s3'::character varying;


--
-- Name: _hyper_1_1_chunk is_adjusted; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk ALTER COLUMN is_adjusted SET DEFAULT true;


--
-- Name: connection_test id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connection_test ALTER COLUMN id SET DEFAULT nextval('public.connection_test_id_seq'::regclass);


--
-- Name: model_parameters id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_parameters ALTER COLUMN id SET DEFAULT nextval('public.model_parameters_id_seq'::regclass);


--
-- Name: _hyper_1_1_chunk 1_1_ohlcv_daily_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk
    ADD CONSTRAINT "1_1_ohlcv_daily_pkey" PRIMARY KEY ("time", symbol_id);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: accounts accounts_user_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_name_key UNIQUE (user_id, name);


--
-- Name: assets assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (id);


--
-- Name: assets assets_symbol_exchange_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_symbol_exchange_id_key UNIQUE (symbol, exchange_id);


--
-- Name: connection_test connection_test_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connection_test
    ADD CONSTRAINT connection_test_pkey PRIMARY KEY (id);


--
-- Name: daily_snapshots daily_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_snapshots
    ADD CONSTRAINT daily_snapshots_pkey PRIMARY KEY ("time", symbol_id);


--
-- Name: exchanges exchanges_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_code_key UNIQUE (code);


--
-- Name: exchanges exchanges_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_name_key UNIQUE (name);


--
-- Name: exchanges exchanges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_pkey PRIMARY KEY (id);


--
-- Name: job_runs job_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_runs
    ADD CONSTRAINT job_runs_pkey PRIMARY KEY (id);


--
-- Name: market_data market_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_data
    ADD CONSTRAINT market_data_pkey PRIMARY KEY ("time", asset_id);


--
-- Name: model_parameters model_parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_parameters
    ADD CONSTRAINT model_parameters_pkey PRIMARY KEY (id);


--
-- Name: ohlcv_daily ohlcv_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ohlcv_daily
    ADD CONSTRAINT ohlcv_daily_pkey PRIMARY KEY ("time", symbol_id);


--
-- Name: ohlcv ohlcv_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ohlcv
    ADD CONSTRAINT ohlcv_pkey PRIMARY KEY (ticker_id, date);


--
-- Name: options_chains options_chains_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.options_chains
    ADD CONSTRAINT options_chains_pkey PRIMARY KEY ("time", symbol_id, expiration_date, strike_price, option_type);


--
-- Name: options_daily_summary options_daily_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.options_daily_summary
    ADD CONSTRAINT options_daily_summary_pkey PRIMARY KEY ("time", symbol_id);


--
-- Name: order_book_snapshots order_book_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_book_snapshots
    ADD CONSTRAINT order_book_snapshots_pkey PRIMARY KEY ("time", asset_id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: portfolio_tickers portfolio_tickers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_tickers
    ADD CONSTRAINT portfolio_tickers_pkey PRIMARY KEY (id);


--
-- Name: portfolio_tickers portfolio_tickers_portfolio_id_ticker_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_tickers
    ADD CONSTRAINT portfolio_tickers_portfolio_id_ticker_id_key UNIQUE (portfolio_id, ticker_id);


--
-- Name: portfolios portfolios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolios
    ADD CONSTRAINT portfolios_pkey PRIMARY KEY (id);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: recommendation_outcomes recommendation_outcomes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendation_outcomes
    ADD CONSTRAINT recommendation_outcomes_pkey PRIMARY KEY (id);


--
-- Name: recommendations recommendations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT recommendations_pkey PRIMARY KEY (id);


--
-- Name: signals signals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_pkey PRIMARY KEY (id);


--
-- Name: strategies strategies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategies
    ADD CONSTRAINT strategies_pkey PRIMARY KEY (id);


--
-- Name: strategies strategies_user_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategies
    ADD CONSTRAINT strategies_user_id_name_key UNIQUE (user_id, name);


--
-- Name: tickers tickers_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickers
    ADD CONSTRAINT tickers_id_key UNIQUE (id);


--
-- Name: tickers tickers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickers
    ADD CONSTRAINT tickers_pkey PRIMARY KEY (symbol);


--
-- Name: trade_history trade_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade_history
    ADD CONSTRAINT trade_history_pkey PRIMARY KEY ("time", asset_id, trade_id);


--
-- Name: trades trades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_pkey PRIMARY KEY (id);


--
-- Name: model_parameters unique_model_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_parameters
    ADD CONSTRAINT unique_model_version UNIQUE (model_name, version);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: _hyper_1_1_chunk_idx_ohlcv_daily_symbol; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_1_chunk_idx_ohlcv_daily_symbol ON _timescaledb_internal._hyper_1_1_chunk USING btree (symbol_id, "time" DESC);


--
-- Name: _hyper_1_1_chunk_idx_ohlcv_ticker_id; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_1_chunk_idx_ohlcv_ticker_id ON _timescaledb_internal._hyper_1_1_chunk USING btree (ticker_id, "time" DESC) WHERE (ticker_id IS NOT NULL);


--
-- Name: _hyper_1_1_chunk_ohlcv_daily_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_1_chunk_ohlcv_daily_time_idx ON _timescaledb_internal._hyper_1_1_chunk USING btree ("time" DESC);


--
-- Name: _materialized_hypertable_13_asset_id_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_13_asset_id_bucket_idx ON _timescaledb_internal._materialized_hypertable_13 USING btree (asset_id, bucket DESC);


--
-- Name: _materialized_hypertable_13_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_13_bucket_idx ON _timescaledb_internal._materialized_hypertable_13 USING btree (bucket DESC);


--
-- Name: _materialized_hypertable_14_asset_id_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_14_asset_id_bucket_idx ON _timescaledb_internal._materialized_hypertable_14 USING btree (asset_id, bucket DESC);


--
-- Name: _materialized_hypertable_14_bucket_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _materialized_hypertable_14_bucket_idx ON _timescaledb_internal._materialized_hypertable_14 USING btree (bucket DESC);


--
-- Name: compress_hyper_10_2_chunk_symbol_id__ts_meta_min_1__ts_meta_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX compress_hyper_10_2_chunk_symbol_id__ts_meta_min_1__ts_meta_idx ON _timescaledb_internal.compress_hyper_10_2_chunk USING btree (symbol_id, _ts_meta_min_1 DESC, _ts_meta_max_1 DESC, _ts_meta_min_2, _ts_meta_max_2);


--
-- Name: daily_snapshots_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX daily_snapshots_time_idx ON public.daily_snapshots USING btree ("time" DESC);


--
-- Name: idx_daily_snapshots_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_daily_snapshots_symbol ON public.daily_snapshots USING btree (symbol_id, "time" DESC);


--
-- Name: idx_job_runs_job_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_job_runs_job_name ON public.job_runs USING btree (job_name);


--
-- Name: idx_job_runs_started_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_job_runs_started_at ON public.job_runs USING btree (started_at DESC);


--
-- Name: idx_job_runs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_job_runs_status ON public.job_runs USING btree (status);


--
-- Name: idx_ohlcv_daily_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ohlcv_daily_symbol ON public.ohlcv_daily USING btree (symbol_id, "time" DESC);


--
-- Name: idx_ohlcv_ticker_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ohlcv_ticker_id ON public.ohlcv_daily USING btree (ticker_id, "time" DESC) WHERE (ticker_id IS NOT NULL);


--
-- Name: idx_options_chains_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_options_chains_symbol ON public.options_chains USING btree (symbol_id, "time" DESC);


--
-- Name: idx_options_summary_gex; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_options_summary_gex ON public.options_daily_summary USING btree (calculated_gex, "time" DESC);


--
-- Name: idx_options_summary_pcr; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_options_summary_pcr ON public.options_daily_summary USING btree (put_call_oi_ratio, "time" DESC);


--
-- Name: idx_options_summary_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_options_summary_symbol ON public.options_daily_summary USING btree (symbol_id, "time" DESC);


--
-- Name: idx_orders_asset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_orders_asset_id ON public.orders USING btree (asset_id);


--
-- Name: idx_orders_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_orders_created_at ON public.orders USING btree (created_at);


--
-- Name: idx_orders_portfolio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_orders_portfolio_id ON public.orders USING btree (portfolio_id);


--
-- Name: idx_outcomes_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outcomes_date ON public.recommendation_outcomes USING btree (evaluation_date DESC);


--
-- Name: idx_outcomes_recommendation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outcomes_recommendation ON public.recommendation_outcomes USING btree (recommendation_id);


--
-- Name: idx_positions_asset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_positions_asset_id ON public.positions USING btree (asset_id);


--
-- Name: idx_positions_portfolio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_positions_portfolio_id ON public.positions USING btree (portfolio_id);


--
-- Name: idx_recommendations_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_recommendations_status ON public.recommendations USING btree (status, recommendation_date DESC);


--
-- Name: idx_recommendations_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_recommendations_symbol ON public.recommendations USING btree (symbol_id, recommendation_date DESC);


--
-- Name: idx_signals_asset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_signals_asset_id ON public.signals USING btree (asset_id);


--
-- Name: idx_signals_strategy_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_signals_strategy_id ON public.signals USING btree (strategy_id);


--
-- Name: idx_snapshots_adx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snapshots_adx ON public.daily_snapshots USING btree (adx_14, "time" DESC) WHERE (adx_14 IS NOT NULL);


--
-- Name: idx_snapshots_dgpi; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snapshots_dgpi ON public.daily_snapshots USING btree (dgpi, "time" DESC) WHERE (dgpi IS NOT NULL);


--
-- Name: idx_snapshots_gamma_flip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snapshots_gamma_flip ON public.daily_snapshots USING btree (gamma_flip_level, "time" DESC) WHERE (gamma_flip_level IS NOT NULL);


--
-- Name: idx_snapshots_iv; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snapshots_iv ON public.daily_snapshots USING btree (average_iv, "time" DESC) WHERE (average_iv IS NOT NULL);


--
-- Name: idx_snapshots_pcr; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snapshots_pcr ON public.daily_snapshots USING btree (put_call_ratio_oi, "time" DESC) WHERE (put_call_ratio_oi IS NOT NULL);


--
-- Name: idx_snapshots_rsi; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snapshots_rsi ON public.daily_snapshots USING btree (rsi_14, "time" DESC) WHERE (rsi_14 IS NOT NULL);


--
-- Name: idx_snapshots_rvol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snapshots_rvol ON public.daily_snapshots USING btree (rvol, "time" DESC) WHERE (rvol IS NOT NULL);


--
-- Name: idx_snapshots_vsi; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snapshots_vsi ON public.daily_snapshots USING btree (vsi, "time" DESC) WHERE (vsi IS NOT NULL);


--
-- Name: idx_trades_asset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trades_asset_id ON public.trades USING btree (asset_id);


--
-- Name: idx_trades_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trades_created_at ON public.trades USING btree (created_at);


--
-- Name: idx_trades_portfolio_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trades_portfolio_id ON public.trades USING btree (portfolio_id);


--
-- Name: market_data_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX market_data_time_idx ON public.market_data USING btree ("time" DESC);


--
-- Name: ohlcv_daily_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ohlcv_daily_time_idx ON public.ohlcv_daily USING btree ("time" DESC);


--
-- Name: options_chains_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX options_chains_time_idx ON public.options_chains USING btree ("time" DESC);


--
-- Name: options_daily_summary_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX options_daily_summary_time_idx ON public.options_daily_summary USING btree ("time" DESC);


--
-- Name: order_book_snapshots_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX order_book_snapshots_time_idx ON public.order_book_snapshots USING btree ("time" DESC);


--
-- Name: trade_history_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX trade_history_time_idx ON public.trade_history USING btree ("time" DESC);


--
-- Name: accounts update_accounts_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_accounts_modtime BEFORE UPDATE ON public.accounts FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: assets update_assets_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_assets_modtime BEFORE UPDATE ON public.assets FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: exchanges update_exchanges_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_exchanges_modtime BEFORE UPDATE ON public.exchanges FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: model_parameters update_model_parameters_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_model_parameters_modtime BEFORE UPDATE ON public.model_parameters FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: orders update_orders_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_orders_modtime BEFORE UPDATE ON public.orders FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: portfolios update_portfolios_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_portfolios_modtime BEFORE UPDATE ON public.portfolios FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: positions update_positions_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_positions_modtime BEFORE UPDATE ON public.positions FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: signals update_signals_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_signals_modtime BEFORE UPDATE ON public.signals FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: strategies update_strategies_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_strategies_modtime BEFORE UPDATE ON public.strategies FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: users update_users_modtime; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_users_modtime BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: accounts accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: assets assets_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_exchange_id_fkey FOREIGN KEY (exchange_id) REFERENCES public.exchanges(id);


--
-- Name: market_data market_data_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_data
    ADD CONSTRAINT market_data_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: ohlcv ohlcv_ticker_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ohlcv
    ADD CONSTRAINT ohlcv_ticker_id_fkey FOREIGN KEY (ticker_id) REFERENCES public.tickers(id) ON DELETE CASCADE;


--
-- Name: order_book_snapshots order_book_snapshots_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_book_snapshots
    ADD CONSTRAINT order_book_snapshots_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: orders orders_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: orders orders_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: orders orders_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES public.portfolios(id) ON DELETE CASCADE;


--
-- Name: portfolio_tickers portfolio_tickers_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_tickers
    ADD CONSTRAINT portfolio_tickers_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES public.portfolios(id) ON DELETE CASCADE;


--
-- Name: portfolio_tickers portfolio_tickers_ticker_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_tickers
    ADD CONSTRAINT portfolio_tickers_ticker_id_fkey FOREIGN KEY (ticker_id) REFERENCES public.tickers(id) ON DELETE CASCADE;


--
-- Name: positions positions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: positions positions_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: positions positions_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES public.portfolios(id) ON DELETE CASCADE;


--
-- Name: recommendation_outcomes recommendation_outcomes_recommendation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendation_outcomes
    ADD CONSTRAINT recommendation_outcomes_recommendation_id_fkey FOREIGN KEY (recommendation_id) REFERENCES public.recommendations(id) ON DELETE CASCADE;


--
-- Name: recommendations recommendations_snapshot_time_symbol_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT recommendations_snapshot_time_symbol_id_fkey FOREIGN KEY (snapshot_time, symbol_id) REFERENCES public.daily_snapshots("time", symbol_id);


--
-- Name: signals signals_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: signals signals_strategy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_strategy_id_fkey FOREIGN KEY (strategy_id) REFERENCES public.strategies(id) ON DELETE CASCADE;


--
-- Name: strategies strategies_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategies
    ADD CONSTRAINT strategies_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: trade_history trade_history_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade_history
    ADD CONSTRAINT trade_history_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: trades trades_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: trades trades_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: trades trades_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES public.portfolios(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

