import Redis from "ioredis"

const redis = new Redis({
  host: process.env.REDIS_HOST || "redis",
  port: parseInt(process.env.REDIS_PORT || "6379", 10),
  username: process.env.REDIS_USER || "nodeapi",
  password: process.env.REDIS_PASSWORD || "",
})

redis.on("connect", () => {
  console.log("[Redis] Connected")
})

redis.on("error", (err) => {
  console.error("[Redis Error]", err)
})

export default redis
