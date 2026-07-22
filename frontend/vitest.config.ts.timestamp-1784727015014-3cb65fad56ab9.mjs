// vitest.config.ts
import { defineConfig } from "file:///C:/Users/LiShuai/Desktop/Agents/starmap/frontend/node_modules/vitest/dist/config.js";
import vue from "file:///C:/Users/LiShuai/Desktop/Agents/starmap/frontend/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import { fileURLToPath, URL } from "node:url";
var __vite_injected_original_import_meta_url = "file:///C:/Users/LiShuai/Desktop/Agents/starmap/frontend/vitest.config.ts";
var vitest_config_default = defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", __vite_injected_original_import_meta_url))
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/__tests__/**/*.test.ts", "src/**/__tests__/**/*.spec.ts"],
    exclude: [
      "node_modules",
      "dist",
      "e2e/**",
      "cypress/**"
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      include: ["src/**/__tests__/**/*.test.ts", "src/**/__tests__/**/*.spec.ts"],
      thresholds: {
        lines: 60,
        functions: 60,
        branches: 60,
        statements: 60
      }
    }
  }
});
export {
  vitest_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZXN0LmNvbmZpZy50cyJdLAogICJzb3VyY2VzQ29udGVudCI6IFsiY29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2Rpcm5hbWUgPSBcIkM6XFxcXFVzZXJzXFxcXExpU2h1YWlcXFxcRGVza3RvcFxcXFxBZ2VudHNcXFxcc3Rhcm1hcFxcXFxmcm9udGVuZFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiQzpcXFxcVXNlcnNcXFxcTGlTaHVhaVxcXFxEZXNrdG9wXFxcXEFnZW50c1xcXFxzdGFybWFwXFxcXGZyb250ZW5kXFxcXHZpdGVzdC5jb25maWcudHNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL0M6L1VzZXJzL0xpU2h1YWkvRGVza3RvcC9BZ2VudHMvc3Rhcm1hcC9mcm9udGVuZC92aXRlc3QuY29uZmlnLnRzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZXN0L2NvbmZpZydcbmltcG9ydCB2dWUgZnJvbSAnQHZpdGVqcy9wbHVnaW4tdnVlJ1xuaW1wb3J0IHsgZmlsZVVSTFRvUGF0aCwgVVJMIH0gZnJvbSAnbm9kZTp1cmwnXG5cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFt2dWUoKV0sXG4gIHJlc29sdmU6IHtcbiAgICBhbGlhczoge1xuICAgICAgJ0AnOiBmaWxlVVJMVG9QYXRoKG5ldyBVUkwoJy4vc3JjJywgaW1wb3J0Lm1ldGEudXJsKSksXG4gICAgfSxcbiAgfSxcbiAgdGVzdDoge1xuICAgIGVudmlyb25tZW50OiAnanNkb20nLFxuICAgIGdsb2JhbHM6IHRydWUsXG4gICAgaW5jbHVkZTogWydzcmMvKiovX190ZXN0c19fLyoqLyoudGVzdC50cycsICdzcmMvKiovX190ZXN0c19fLyoqLyouc3BlYy50cyddLFxuICAgIGV4Y2x1ZGU6IFtcbiAgICAgICdub2RlX21vZHVsZXMnLFxuICAgICAgJ2Rpc3QnLFxuICAgICAgJ2UyZS8qKicsXG4gICAgICAnY3lwcmVzcy8qKicsXG4gICAgXSxcbiAgICBjb3ZlcmFnZToge1xuICAgICAgcHJvdmlkZXI6ICd2OCcsXG4gICAgICByZXBvcnRlcjogWyd0ZXh0JywgJ2pzb24nLCAnaHRtbCddLFxuICAgICAgaW5jbHVkZTogWydzcmMvKiovX190ZXN0c19fLyoqLyoudGVzdC50cycsICdzcmMvKiovX190ZXN0c19fLyoqLyouc3BlYy50cyddLFxuICAgICAgdGhyZXNob2xkczoge1xuICAgICAgICBsaW5lczogNjAsXG4gICAgICAgIGZ1bmN0aW9uczogNjAsXG4gICAgICAgIGJyYW5jaGVzOiA2MCxcbiAgICAgICAgc3RhdGVtZW50czogNjAsXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG59KVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUFvVixTQUFTLG9CQUFvQjtBQUNqWCxPQUFPLFNBQVM7QUFDaEIsU0FBUyxlQUFlLFdBQVc7QUFGb0wsSUFBTSwyQ0FBMkM7QUFJeFEsSUFBTyx3QkFBUSxhQUFhO0FBQUEsRUFDMUIsU0FBUyxDQUFDLElBQUksQ0FBQztBQUFBLEVBQ2YsU0FBUztBQUFBLElBQ1AsT0FBTztBQUFBLE1BQ0wsS0FBSyxjQUFjLElBQUksSUFBSSxTQUFTLHdDQUFlLENBQUM7QUFBQSxJQUN0RDtBQUFBLEVBQ0Y7QUFBQSxFQUNBLE1BQU07QUFBQSxJQUNKLGFBQWE7QUFBQSxJQUNiLFNBQVM7QUFBQSxJQUNULFNBQVMsQ0FBQyxpQ0FBaUMsK0JBQStCO0FBQUEsSUFDMUUsU0FBUztBQUFBLE1BQ1A7QUFBQSxNQUNBO0FBQUEsTUFDQTtBQUFBLE1BQ0E7QUFBQSxJQUNGO0FBQUEsSUFDQSxVQUFVO0FBQUEsTUFDUixVQUFVO0FBQUEsTUFDVixVQUFVLENBQUMsUUFBUSxRQUFRLE1BQU07QUFBQSxNQUNqQyxTQUFTLENBQUMsaUNBQWlDLCtCQUErQjtBQUFBLE1BQzFFLFlBQVk7QUFBQSxRQUNWLE9BQU87QUFBQSxRQUNQLFdBQVc7QUFBQSxRQUNYLFVBQVU7QUFBQSxRQUNWLFlBQVk7QUFBQSxNQUNkO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFDRixDQUFDOyIsCiAgIm5hbWVzIjogW10KfQo=
