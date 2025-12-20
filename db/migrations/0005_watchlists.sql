CREATE TABLE public.watchlists (
    watchlist_id VARCHAR(255) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_date DATE NOT NULL,
    UNIQUE (watchlist_id, symbol)
);

CREATE INDEX idx_watchlists_watchlist_id_active
    ON public.watchlists (watchlist_id)
    WHERE active = TRUE;

CREATE INDEX idx_watchlists_symbol
    ON public.watchlists (symbol);