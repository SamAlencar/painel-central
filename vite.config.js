import { defineConfig } from "vite"

// base relativa: o mesmo build abre na raiz e em https://<user>.github.io/<repo>/.
export default defineConfig({
  base: "./",
  server: { host: "127.0.0.1", port: 4471, strictPort: true },
  preview: { host: "127.0.0.1", port: 4471, strictPort: true },
})
