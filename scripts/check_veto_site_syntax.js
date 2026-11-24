const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..", "veto-history-site");
const files = ["app.js", "data.js", "extra-data.js", "map-info-data.js"];

for (const file of files) {
  const fullPath = path.join(root, file);
  const source = fs.readFileSync(fullPath, "utf8");
  try {
    new Function(source);
    console.log(`${file}: ok`);
  } catch (error) {
    console.error(`${file}: ${error.message}`);
    process.exitCode = 1;
  }
}
