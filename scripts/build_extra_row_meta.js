const fs = require("fs");
const path = require("path");
const vm = require("vm");

const workspaceRoot = path.resolve(__dirname, "..");
const sourcePath = path.join(workspaceRoot, "veto-history-site", "extra-data.js");
const outputPath = path.join(workspaceRoot, "veto-history-site", "extra-row-meta.js");

const source = fs.readFileSync(sourcePath, "utf8");
const context = {};
vm.createContext(context);
vm.runInContext(`${source}\nthis.__data = extraVetoHistoryData;`, context);

const extraVetoHistoryData = context.__data ?? {};
const targetTeams = ["attax", "dortmund"];
const result = {};

for (const teamKey of targetTeams) {
  const team = extraVetoHistoryData[teamKey];
  if (!team?.rows) continue;

  result[teamKey] = {};

  for (const row of team.rows) {
    const rowKey = `${row.date}|${row.opponentAbbr ?? row.opponent}`;
    result[teamKey][rowKey] = {
      pick1: {
        score: row.pick1?.score ?? "",
        teamStartSide: row.pick1?.teamStartSide ?? ""
      },
      pick2: {
        score: row.pick2?.score ?? "",
        teamStartSide: row.pick2?.teamStartSide ?? ""
      },
      decider: {
        score: row.deciderScore ?? "",
        teamStartSide: ""
      }
    };
  }
}

const output = `const extraVetoRowMeta = ${JSON.stringify(result, null, 2)};\n`;
fs.writeFileSync(outputPath, output, "utf8");
console.log(`Wrote ${path.relative(workspaceRoot, outputPath)}`);
