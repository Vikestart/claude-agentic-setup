@@@ agents/opus-medium-executor.md
name: an executor loses its tools list and inherits everything again
expect: no explicit tools: list
<<<<<<< OLD
tools: Bash, Read, Edit, Write,
======= NEW
oldtools: Bash, Read, Edit, Write,
>>>>>>> END

@@@ agents/opus-high-reviewer.md
name: a reviewer gains editing tools
expect: reviewers never edit
<<<<<<< OLD
tools: Bash, Read, Glob,
======= NEW
tools: Bash, Read, Edit, Write, Glob,
>>>>>>> END

@@@ agents/opus-high-executor.md
name: an executor loses the built-in browser
expect: a core tool is missing
<<<<<<< OLD
SendMessage, mcp__Claude_Browser, mcp__plugin
======= NEW
SendMessage, mcp__plugin
>>>>>>> END

@@@ agents/opus-xhigh-reviewer.md
name: a reviewer carries the artifact tool again
expect: carries {'Artifact'}
<<<<<<< OLD
tools: Bash, Read, Glob,
======= NEW
tools: Bash, Read, Artifact, Glob,
>>>>>>> END

@@@ agents/sonnet-medium-executor.md
name: an executor carries computer use
expect: carries a dropped MCP group
<<<<<<< OLD
SendMessage, mcp__Claude_Browser,
======= NEW
SendMessage, mcp__computer-use, mcp__Claude_Browser,
>>>>>>> END

@@@ agents/opus-xhigh-reviewer.md
name: a reviewer gains only Write
expect: reviewers never edit
<<<<<<< OLD
tools: Bash, Read, Glob,
======= NEW
tools: Bash, Read, Write, Glob,
>>>>>>> END

@@@ agents/sonnet-medium-executor.md
name: an executor loses Write
expect: an executor cannot edit
<<<<<<< OLD
Read, Edit, Write, Glob,
======= NEW
Read, Edit, Glob,
>>>>>>> END

@@@ agents/opus-medium-executor.md
name: an agent carries PowerShell again
expect: carries {'PowerShell'}
<<<<<<< OLD
tools: Bash, Read,
======= NEW
tools: Bash, PowerShell, Read,
>>>>>>> END

@@@ agents/opus-high-reviewer.md
name: a common agent carries the web tools again
expect: a common agent carries the web tools
<<<<<<< OLD
SendMessage, mcp__Claude_Browser,
======= NEW
SendMessage, WebFetch, WebSearch, mcp__Claude_Browser,
>>>>>>> END
