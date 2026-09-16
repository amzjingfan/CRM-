import frontendConfig from "./frontend/eslint.config.mjs";

const eslintConfig = [
  {
    ignores: ["frontend/.next/**", "frontend/node_modules/**", "frontend/next-env.d.ts"],
  },
  ...frontendConfig,
  {
    settings: {
      next: {
        rootDir: "frontend/",
      },
    },
  },
];

export default eslintConfig;
