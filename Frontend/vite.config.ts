import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  vite: {
    resolve: {
      alias: [
        {
          find: /^use-sync-external-store\/shim\/with-selector(\.js)?$/,
          replacement: path.resolve(
            __dirname,
            "src/lib/shims/use-sync-external-store-with-selector.ts"
          ),
        },
      ],
    },
  },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
