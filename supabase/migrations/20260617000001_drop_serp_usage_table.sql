-- Drop the serp_usage table: SerpAPI has been removed from the codebase
-- (the platform uses Tavily exclusively for scout retrieval). The table
-- tracked per-user/day SERP request budgets and now has no readers or writers.
-- Reversible: recreate from migration history if SerpAPI is ever reintroduced.
drop table if exists public.serp_usage;
