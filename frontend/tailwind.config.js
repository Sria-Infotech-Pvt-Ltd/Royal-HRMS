/** @type {import('tailwindcss').Config} */
module.exports = {
  mode: 'jit',
  purge: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    // Test files never carry styles. Excluding them stops Tailwind from watching a test file that is created and
    // deleted while the dev server runs, which crashed globals.css with "ENOENT: stat ..._view.test.ts".
    "!./app/**/*.test.{js,ts,jsx,tsx}",
    "!./components/**/*.test.{js,ts,jsx,tsx}",
    "!./lib/**/*.test.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: false,
  theme: { extend: {} },
  variants: { extend: {} },
  plugins: [],
};
