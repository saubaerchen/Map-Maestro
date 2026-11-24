const fs = require("fs");
const path = require("path");

const inputPath = path.resolve(process.cwd(), "veto-history-site", "data.js");
const outputPath = path.resolve(process.cwd(), "veto-history-site", "data.min.js");

const raw = fs.readFileSync(inputPath, "utf8");
const prefix = "const vetoHistoryData = ";
const suffix = ";";

if (!raw.startsWith(prefix) || !raw.trimEnd().endsWith(suffix)) {
  throw new Error("Unexpected data.js format");
}

const jsonText = raw.slice(prefix.length, raw.trimEnd().lastIndexOf(suffix));
const data = JSON.parse(jsonText);
const minified = `const vetoHistoryData=${JSON.stringify(data)};`;

fs.writeFileSync(outputPath, minified, "utf8");
process.stdout.write(Buffer.from(minified, "utf8").toString("base64"));
