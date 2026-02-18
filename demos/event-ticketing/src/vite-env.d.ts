/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MAPBOX_TOKEN: string;
  readonly VITE_ATMX_API_KEY: string;
  readonly VITE_RISK_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
