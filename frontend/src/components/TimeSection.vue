<script setup lang="ts">
import type { Component } from 'vue'
import { CalendarClock, CircleDot, History } from '@lucide/vue'

// A page reads in time, like the three Norns of the name: what is now, what
// is planned and expected (future), what happened and what was learned from
// it (past).  Every device page has these three sections, in this order.
const props = defineProps<{
  when: 'now' | 'future' | 'past'
  /** One line on what the section holds for this page. */
  hint?: string
}>()

const SECTIONS: Record<string, { title: string, icon: Component }> = {
  now: { title: 'Now', icon: CircleDot },
  future: { title: 'Future', icon: CalendarClock },
  past: { title: 'Past', icon: History },
}
</script>

<template>
  <section class="time-section" :class="'time-' + props.when" :aria-label="SECTIONS[props.when].title" :data-testid="'section-' + props.when">
    <header class="time-head">
      <component :is="SECTIONS[props.when].icon" class="size-4" aria-hidden="true" />
      <h2>{{ SECTIONS[props.when].title }}</h2>
      <span v-if="hint" class="time-hint">{{ hint }}</span>
    </header>
    <slot />
  </section>
</template>

<style scoped>
.time-section { margin-bottom: 22px; }
.time-head { display: flex; align-items: center; gap: 8px; margin: 0 2px 10px; color: var(--muted-foreground); }
.time-head h2 { font-size: .78rem; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; color: var(--foreground); }
.time-hint { font-size: .8rem; }
.time-head::after { content: ''; flex: 1; height: 1px; background: var(--border); }
.time-now .time-head svg { color: var(--primary); }
</style>
