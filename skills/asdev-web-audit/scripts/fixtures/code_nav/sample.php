<?php
// Header paragraph for the PHP fixture. <start:block:Header paragraph>
// Every item is marked: test_code_nav.py derives expected ranges from these markers.
declare(strict_types=1);
$setup = 1; // <end:block:Header paragraph>

function brace_in_string(): string // <start:function:brace_in_string>
{
    $a = '}}}{ \' }';
    $b = "{ \" } {$setup}";
    return $a . $b . `echo }`;
} // <end:function:brace_in_string>

/**
 * Docblock with a brace } and the words function fake_doc() and class Fake {
 */
function brace_in_comment(): int // <start:function:brace_in_comment>
{
    // a } in a line comment
    # a } in a hash comment
    /* a { in a block comment */
    return 1;
} // <end:function:brace_in_comment>

function brace_in_heredoc(): string // <start:function:brace_in_heredoc>
{
    $html = <<<HTML
    <div>{$setup} }} class Ghost {}</div>
    HTML;
    $raw = <<<'RAW'
final class Phantom
{
    public function haunt() {}
}
RAW;
    return $html . $raw;
} // <end:function:brace_in_heredoc>

abstract class Shape implements \Countable // <start:class:Shape>
{
    abstract public function area(): float; // <start:method:Shape::area> <end:method:Shape::area>

    public function count(): int // <start:method:Shape::count>
    {
        $fn = fn (int $x): int => $x * 2; // <start:closure:$fn> <end:closure:$fn>
        $cb = function (int $y) use ($fn): int { // <start:closure:$cb>
            return $fn($y) + strlen('}');
        }; // <end:closure:$cb>
        return $cb(1);
    } // <end:method:Shape::count>

    #[Deprecated]
    public static function run(): void // <start:method:Shape::run>
    {
        if (true) {
            $x = ['a' => ['b' => '{']];
        }
    } // <end:method:Shape::run>
} // <end:class:Shape>

interface Runner // <start:interface:Runner>
{
    public function run(): void; // <start:method:Runner::run> <end:method:Runner::run>
} // <end:interface:Runner>

// ==== Test section ==== <start:banner:Test section>

// First test paragraph, line one. <start:block:First test paragraph>
// Second line of the same paragraph.
$obj = new class { // <start:class:class@anonymous>
    public function inner(): int { return 1; } // <start:method:class@anonymous::inner> <end:method:class@anonymous::inner>
}; // <end:class:class@anonymous>
check('first check name', $obj->inner() === 1 && Shape::class !== ''); // <end:block:First test paragraph>
// Second test paragraph follows code directly. <start:block:Second test paragraph>
$s = '// not a comment { ';
check('second check name', $s !== ''); // <end:block:Second test paragraph> <end:banner:Test section>

# ---- Second banner ---- <start:banner:Second banner>
// Block under the second banner. <start:block:Block under the second banner>
check('third check', true);
?>
<p>Inline HTML with a brace } and an 'apostrophe</p>
<?php
if (true) {
// a column-0 comment inside a brace is not a block
    check('fourth check', true);
} // <end:block:Block under the second banner> <end:banner:Second banner>
