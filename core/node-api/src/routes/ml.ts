import express from "express"

import redis from "../redis/client"

import {
  getJsonKey,
  getStringKey
} from "../utils/redisHelpers"

const router = express.Router()

// ----------------------------------
// PCA SUMMARY
// ----------------------------------

router.get("/pca/summary", async (_, res) => {

  try {

    const [
      projection,
      components,
      variance,
      eigenvalues,
      totalVariance,
      mean,
      std,
      drift,
      risk,
      confidence
    ] = await Promise.all([
      getJsonKey("pca:latest"),
      getJsonKey("pca:components"),
      getJsonKey("pca:variance"),
      getJsonKey("pca:eigenvalues"),
      getStringKey("pca:total_variance"),
      getJsonKey("pca:mean"),
      getJsonKey("pca:std"),
      getStringKey("drift:score"),
      getStringKey("model:prediction"),
      getStringKey("model:confidence")
    ])

    return res.json({
      projection,
      components,
      variance,
      eigenvalues,
      totalVariance: Number(totalVariance || 0),
      mean,
      std,
      drift: Number(drift || 0),
      risk,
      confidence: Number(confidence || 0)
    })

  } catch (err) {

    console.error(err)

    return res.status(500).json({
      error: "Failed to fetch PCA summary"
    })
  }
})

// ----------------------------------
// PCA HISTORY
// ----------------------------------

router.get("/pca/history", async (_, res) => {

  try {

    const history = await redis.lrange(
      "pca:history",
      0,
      99
    )

    return res.json(
      history.map(item => JSON.parse(item))
    )

  } catch (err) {

    return res.status(500).json({
      error: "Failed to fetch history"
    })
  }
})

// ----------------------------------
// INDIVIDUAL PCA ROUTES
// ----------------------------------

router.get("/pca/projection", async (_, res) => {
  res.json(
    await getJsonKey("pca:latest")
  )
})

router.get("/pca/components", async (_, res) => {
  res.json(
    await getJsonKey("pca:components")
  )
})

router.get("/pca/variance", async (_, res) => {
  res.json(
    await getJsonKey("pca:variance")
  )
})

router.get("/pca/eigenvalues", async (_, res) => {
  res.json(
    await getJsonKey("pca:eigenvalues")
  )
})

// ----------------------------------
// DRIFT
// ----------------------------------

router.get("/drift", async (_, res) => {

  const [
    drift,
    classification
  ] = await Promise.all([
    getStringKey("drift:score"),
    getStringKey("drift:classification")
  ])

  res.json({
    drift: Number(drift || 0),
    classification
  })
})

# ----------------------------------
# RISK
# ----------------------------------

router.get("/risk", async (_, res) => {

  const [
    prediction,
    confidence
  ] = await Promise.all([
    getStringKey("model:prediction"),
    getStringKey("model:confidence")
  ])

  res.json({
    prediction,
    confidence: Number(confidence || 0)
  })
})

export default router
