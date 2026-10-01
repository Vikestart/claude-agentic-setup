// JS fixture header. <start:block:JS fixture header>
import { a } from './a.js';
const LIMIT = 3; // <end:block:JS fixture header>

export function template_nesting(x) { // <start:function:template_nesting>
  const s = `a ${x ? `inner ${'}'} {` : '{'} b } ${ { k: 1 }.k }`;
  return s + LIMIT;
} // <end:function:template_nesting>

function regex_braces(s) { // <start:function:regex_braces>
  const r = /\}+[{}/]/g;
  const half = s.length / 2; const q = s.length / 2 / 1;
  return r.test(s) && half > q;
} // <end:function:regex_braces>

class Widget extends Base { // <start:class:Widget>
  static create(opts = {}) { // <start:method:Widget.create>
    return new Widget(opts);
  } // <end:method:Widget.create>

  async render() { // <start:method:Widget.render>
    if (this.ready) {
      return '}';
    }
    return "{";
  } // <end:method:Widget.render>

  onClick = (e) => { // <start:method:Widget.onClick>
    e.preventDefault();
  }; // <end:method:Widget.onClick>
} // <end:class:Widget>

const helper = (a, b) => a + b; // <start:closure:helper> <end:closure:helper>
const handler = async function () { // <start:closure:handler>
  return '/* not a comment */';
}; // <end:closure:handler>

// ---- Banner in JS ---- <start:banner:Banner in JS>
function render() { // <start:function:render>
  return helper(1, 2) + handler + a;
} // <end:function:render> <end:banner:Banner in JS>
