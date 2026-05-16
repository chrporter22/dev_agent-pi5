import Redis from "ioredis"

const redis = new Redis(
  process.env.REDIS_URL || "redis://redis:6379"
)

redis.on("connect", () => {
  console.log("[Redis] Connected")
})

redis.on("error", (err) => {
  console.error("[Redis Error]", err)
})

export default redis
