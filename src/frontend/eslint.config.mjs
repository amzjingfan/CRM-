import coreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

const eslintConfig = [
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"],
  },
  ...coreWebVitals,
  ...nextTypeScript,
  {
    // Next.js 16 新增的 effect 风格规则会把现有异步加载模式整体升级为错误。
    // 本次安全升级不改变页面取数时序；后续交互重构任务再逐页消除这些 effect。
    rules: {
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

export default eslintConfig;
