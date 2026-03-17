import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { createReadStream } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const imagesRoot = join(__dirname, '..', 'data', 'images')

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
      },
    },
  ],
})
