import express from "express"
import cors from "cors"
import dotenv from "dotenv"

import mlRoutes from "./routes/ml"

dotenv.config()

const app = express()

app.use(cors())

app.use(express.json())

app.use("/api/ml", mlRoutes)

app.get("/health", (_, res) => {
  res.json({
    status: "ok"
  })
})

const PORT = process.env.PORT || 3000

app.listen(PORT, () => {
  console.log(
    `[Node API] Running on port ${PORT}`
  )
})
