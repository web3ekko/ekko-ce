-- Deduplication Check Script
-- ONLY checks for duplicates - no job storage, no statistics
-- 
-- KEYS[1] = instance_id
-- ARGV[1] = content_hash (SHA256 of the content to check)
-- ARGV[2] = ttl (seconds for deduplication window, default 300)
--
-- Returns: {true, "ALLOWED"} or {false, "DUPLICATE"}

local instance_id = KEYS[1]
local content_hash = ARGV[1]
local ttl = tonumber(ARGV[2]) or 300  -- Default 5 minutes

-- Generate deduplication key
local dedup_key = "dedup:alert:" .. instance_id .. ":" .. content_hash

-- Check if duplicate exists within TTL window
if redis.call("EXISTS", dedup_key) == 1 then
    return {false, "DUPLICATE"}
end

-- Set deduplication key with TTL
redis.call("SETEX", dedup_key, ttl, "1")

return {true, "ALLOWED"}