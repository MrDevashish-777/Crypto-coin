/* eslint-disable no-console */
const base = process.env.ADMIN_BASE_URL || "http://localhost:3001";

async function check(path, options = {}) {
  const url = `${base}${path}`;
  try {
    const res = await fetch(url, options);
    console.log(`${path} -> ${res.status}`);
  } catch (err) {
    console.error(`${path} -> failed`, err.message);
    process.exitCode = 1;
  }
}

await check("/login");
await check("/api/auth/session");
await check("/dashboard");

