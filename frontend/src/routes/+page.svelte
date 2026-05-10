<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  onMount(() => goto('/plan', { replaceState: true }));
</script>
