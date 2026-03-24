import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { cpSync, createReadStream, existsSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const imagesRoot = join(__dirname, '..', 'data', 'images')
const recThumbRoot = join(__dirname, '..', 'data', 'rec-thumbnails')
const baselineThumbRoot = join(__dirname, '..', 'data', 'baseline-thumbnails')

export default defineConfig({
  publicDir: false,
  plugins: [
    react(),
    {
      name: 'serve-product-images',
      configureServer(server) {
        server.middlewares.use('/images', (req, res, next) => {
          const filePath = join(imagesRoot, req.url)
          res.setHeader('Content-Type', 'image/jpeg')
          const stream = createReadStream(filePath)
          stream.on('error', () => {
            res.statusCode = 404
            res.end('Not found')
          })
          stream.pipe(res)
        })
        server.middlewares.use('/rec-thumbnails', (req, res, next) => {
          const filePath = join(recThumbRoot, req.url)
          res.setHeader('Content-Type', 'image/jpeg')
          const stream = createReadStream(filePath)
          stream.on('error', () => {
            res.statusCode = 404
            res.end('Not found')
          })
          stream.pipe(res)
        })
        server.middlewares.use('/baseline-thumbnails', (req, res, next) => {
          const filePath = join(baselineThumbRoot, req.url)
          res.setHeader('Content-Type', 'image/jpeg')
          const stream = createReadStream(filePath)
          stream.on('error', () => {
            res.statusCode = 404
            res.end('Not found')
          })
          stream.pipe(res)
        })
      },
    },
    {
      name: 'copy-rec-thumbnails',
      closeBundle() {
        // Copy rec-thumbnails into the build output for production
        const dest = join(__dirname, 'dist', 'rec-thumbnails')
        if (existsSync(recThumbRoot)) {
          cpSync(recThumbRoot, dest, { recursive: true })
          console.log('Copied rec-thumbnails to dist/')
        }
        // Copy baseline-thumbnails into the build output for production
        const baselineDest = join(__dirname, 'dist', 'baseline-thumbnails')
        if (existsSync(baselineThumbRoot)) {
          cpSync(baselineThumbRoot, baselineDest, { recursive: true })
          console.log('Copied baseline-thumbnails to dist/')
        }
      },
    },
  ],
})
