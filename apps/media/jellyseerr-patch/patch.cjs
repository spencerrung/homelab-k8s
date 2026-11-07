// Temporary compatibility patch for the pinned Jellyseerr 2.7.3 image.
// Only request-triggered searches for existing series are season-scoped.
const fs = require('node:fs');
const vm = require('node:vm');

function patch(source) {
  const before = 'this.searchSeries(newSeriesResponse.data.id);';
  const after = `for (const seasonNumber of [...new Set(options.seasons)]) {
                            await this.runCommand('SeasonSearch', {
                                seriesId: newSeriesResponse.data.id,
                                seasonNumber,
                            });
                        }`;
  if (source.split(before).length !== 2) {
    throw new Error('Unexpected Jellyseerr Sonarr module: review patch before upgrading');
  }
  const result = source.replace(before, after);
  new vm.Script(result, { filename: 'sonarr.js' });
  return result;
}

if (require.main === module) {
  const source = '/app/dist/api/servarr/sonarr.js';
  fs.writeFileSync('/patched/sonarr.js', patch(fs.readFileSync(source, 'utf8')));
  console.log('Installed request-scoped Sonarr season search patch');
}
module.exports = { patch };
