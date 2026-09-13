// Fix unicode escapes to actual UTF-8 characters
// Handles surrogate pairs (emoji) correctly
const fs = require('fs');
const path = require('path');

function walk(dir) {
  let results = [];
  try {
    for (const f of fs.readdirSync(dir)) {
      const full = path.join(dir, f);
      if (fs.statSync(full).isDirectory()) results.push(...walk(full));
      else if (f.endsWith('.js')) results.push(full);
    }
  } catch(e) {}
  return results;
}

function fixUnicodeEscapes(content) {
  // Match \uXXXX sequences (including surrogate pairs)
  // Pattern: backslash + u + 4 hex digits
  return content.replace(/\\u([0-9a-fA-F]{4})\\u([0-9a-fA-F]{4})/g, (match, hi, lo) => {
    const hiCode = parseInt(hi, 16);
    const loCode = parseInt(lo, 16);
    // Check if it's a surrogate pair
    if (hiCode >= 0xD800 && hiCode <= 0xDBFF && loCode >= 0xDC00 && loCode <= 0xDFFF) {
      return String.fromCodePoint(((hiCode - 0xD800) * 0x400) + (loCode - 0xDC00) + 0x10000);
    }
    // Not a surrogate pair, convert individually
    return String.fromCharCode(hiCode) + String.fromCharCode(loCode);
  }).replace(/\\u([0-9a-fA-F]{4})/g, (match, hex) => {
    const code = parseInt(hex, 16);
    // Skip surrogate halves (already handled above)
    if (code >= 0xD800 && code <= 0xDFFF) return match;
    return String.fromCharCode(code);
  });
}

const dirs = [
  'src/app/(auth)',
  'src/components',
  'src/lib'
];

let totalFixed = 0;
for (const dir of dirs) {
  for (const file of walk(dir)) {
    const content = fs.readFileSync(file, 'utf-8');
    const fixed = fixUnicodeEscapes(content);
    if (fixed !== content) {
      fs.writeFileSync(file, fixed, 'utf-8');
      totalFixed++;
      // Count replacements
      const origCount = (content.match(/\\u[0-9a-fA-F]{4}/g) || []).length;
      const newCount = (fixed.match(/\\u[0-9a-fA-F]{4}/g) || []).length;
      console.log(`Fixed: ${file} (${origCount - newCount} replacements)`);
    }
  }
}
console.log(`\nTotal: ${totalFixed} files fixed`);
