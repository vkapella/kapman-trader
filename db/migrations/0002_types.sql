DO $$
BEGIN
    CREATE TYPE option_type AS ENUM ('C', 'P');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE recommendation_status AS ENUM ('active', 'closed', 'expired');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE recommendation_direction AS ENUM ('LONG', 'SHORT', 'NEUTRAL');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE recommendation_action AS ENUM ('BUY', 'SELL', 'HOLD', 'HEDGE');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE option_strategy AS ENUM ('LONG_CALL', 'LONG_PUT', 'CSP', 'VERTICAL_SPREAD');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE outcome_status AS ENUM ('WIN', 'LOSS', 'NEUTRAL');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;
