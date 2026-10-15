import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API's CORS setting allows http://localhost:5173, so keep this port.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
