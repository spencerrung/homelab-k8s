// Run against the Sonarr module extracted from the pinned application image:
// node apps/media/jellyseerr-patch/test.cjs /tmp/jellyseerr-original-sonarr.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { patch } = require('./patch.cjs');
const source = fs.readFileSync(process.argv[2], 'utf8');
const patched = patch(source);
const exportsObject = {};
vm.runInNewContext(patched, {
  exports: exportsObject,
  require(name) {
    if (name === '../../logger') return { info() {}, debug() {}, error() {} };
    if (name === './base') return class {};
    throw new Error(`Unexpected dependency: ${name}`);
  },
});
const API = exportsObject.default;
async function existing(seasons, searchNow) {
  const api = new API({});
  const commands = [];
  api.getSeriesByTvdbId = async () => ({
    id: 45, title: 'Test series', monitored: true, tags: [],
    seasons: [{ seasonNumber: 2, monitored: false }, { seasonNumber: 3, monitored: true }, { seasonNumber: 4, monitored: false }],
  });
  let updated;
  api.axios = { put: async (_, body) => { updated = body; return { data: body }; } };
  api.runCommand = async (name, args) => commands.push({ name, ...args });
  await api.addSeries({ tvdbid: 123, seasons, searchNow });
  assert.equal(updated.seasons.find(s => s.seasonNumber === 3).monitored, true);
  return JSON.parse(JSON.stringify(commands));
}
(async () => {
  assert.deepEqual(await existing([2], true), [{ name: 'SeasonSearch', seriesId: 45, seasonNumber: 2 }]);
  assert.deepEqual(await existing([2, 2, 4], true), [
    { name: 'SeasonSearch', seriesId: 45, seasonNumber: 2 },
    { name: 'SeasonSearch', seriesId: 45, seasonNumber: 4 },
  ]);
  assert.deepEqual(await existing([2], false), []);
  assert.deepEqual(await existing([], true), []);
  const fresh = new API({});
  fresh.getSeriesByTvdbId = async () => ({ seasons: [{ seasonNumber: 1 }, { seasonNumber: 2 }, { seasonNumber: 3 }] });
  let created;
  fresh.axios = { post: async (_, body) => { created = body; return { data: { ...body, id: 46 } }; } };
  await fresh.addSeries({ tvdbid: 123, seasons: [2], searchNow: true });
  assert.deepEqual(JSON.parse(JSON.stringify(created.seasons.filter(s => s.monitored).map(s => s.seasonNumber))), [2]);
  assert.equal(created.addOptions.searchForMissingEpisodes, true);
  assert.throws(() => patch('changed upstream source'), /Unexpected Jellyseerr/);
  assert.throws(() => patch(source + source), /Unexpected Jellyseerr/);
  assert.throws(() => patch(patched), /Unexpected Jellyseerr/);
  console.log('PASS: requested seasons only, deduplication, search disabled, empty request, preserved monitoring, and incompatible-source guards');
})().catch(error => { console.error(error); process.exitCode = 1; });
