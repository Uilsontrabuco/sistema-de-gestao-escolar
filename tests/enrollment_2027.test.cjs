const test=require('node:test'),assert=require('node:assert/strict');
const {signedStats}=require('../enrollment_2027.js');
test('Enrollment UI preserves signed vacancies and prior fields',()=>{const x={capacity:25,total:31,vacancies:0,excess:6};const y=signedStats(x);assert.equal(y.vacancies,-6);assert.equal(y.excess,6);assert.equal(x.vacancies,0);});
test('PDF totals remain 41 / 1103 / 775 / 37 / 738 / 328',()=>{const d=require('../enrollment_2027_source.json');assert.equal(d.rows.length,41);assert.deepEqual(d.totals,{capacity:1103,students:775,new:37,re:738,vacancies:328});});
