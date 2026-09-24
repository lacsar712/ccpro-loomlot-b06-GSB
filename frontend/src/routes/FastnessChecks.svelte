<script>
  import { onMount } from 'svelte';
  import { api, toLocalInput, fromLocalInput } from '../lib/api.js';
  import { user } from '../lib/auth.js';

  let lots = [];
  let rows = [];
  let error = '';
  // pending=未外发（默认，可建改）；outbound=外发清单（只读、按日过滤）
  let tab = 'pending';
  let outboundDay = utcDateInput(new Date());
  let form = {
    dyeLotId: '',
    checkedAt: toLocalInput(new Date().toISOString()),
    washFastness: 4,
    rubFastness: 3.5,
    tempC: 40,
    notes: '',
  };
  let editing = null;

  function utcDateInput(d) {
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
  }

  async function load() {
    error = '';
    try {
      const qs = tab === 'outbound' ? `?outbound=true&day=${outboundDay}` : '?outbound=false';
      [lots, rows] = await Promise.all([api('/dye-lots'), api(`/fastness-checks${qs}`)]);
      if (!form.dyeLotId && lots.length) form.dyeLotId = String(lots[0].id);
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  function switchTab(next) {
    tab = next;
    load();
  }

  function lotLabel(id) {
    const lot = lots.find((x) => x.id === id);
    return lot ? `${lot.recipeName} (#${lot.id})` : id;
  }

  async function save() {
    error = '';
    try {
      const body = {
        dyeLotId: Number(form.dyeLotId),
        checkedAt: fromLocalInput(form.checkedAt),
        washFastness: Number(form.washFastness),
        rubFastness: Number(form.rubFastness),
        tempC: Number(form.tempC),
        notes: form.notes.trim() || null,
      };
      if (editing) {
        await api(`/fastness-checks/${editing}`, { method: 'PUT', body: JSON.stringify(body) });
      } else {
        await api('/fastness-checks', { method: 'POST', body: JSON.stringify(body) });
      }
      editing = null;
      form = {
        ...form,
        checkedAt: toLocalInput(new Date().toISOString()),
        notes: '',
      };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function startEdit(row) {
    editing = row.id;
    form = {
      dyeLotId: String(row.dyeLotId),
      checkedAt: toLocalInput(row.checkedAt),
      washFastness: row.washFastness,
      rubFastness: row.rubFastness,
      tempC: row.tempC,
      notes: row.notes || '',
    };
  }

  async function remove(id) {
    if (!confirm('确认删除该抽检？')) return;
    error = '';
    try {
      await api(`/fastness-checks/${id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  // 外发：仅主管；写入同坊唯一外发编号，写入后耐洗/摩擦/温度锁定
  async function dispatch(row) {
    const ref = prompt(`为抽检 #${row.id} 填写实验室外发编号（同坊唯一）：`);
    if (ref === null) return;
    const labRefNo = ref.trim();
    if (!labRefNo) {
      error = '外发编号不能为空';
      return;
    }
    error = '';
    try {
      await api(`/fastness-checks/${row.id}/dispatch`, {
        method: 'POST',
        body: JSON.stringify({ labRefNo }),
      });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  $: isAdmin = $user?.role === 'admin';
</script>

<h1 class="page-title">色牢度抽检</h1>
<p class="page-sub">
  耐洗 1–5 级；摩擦牢度须大于 0；记录检测温度。有外发编号即<b>已外发</b>：耐洗、摩擦、温度一律锁定，
  默认列表只看未外发，已外发记录在「外发清单」按日查看。
</p>

<div class="tabs">
  <button class="btn" type="button" class:on={tab === 'pending'} on:click={() => switchTab('pending')}>
    未外发（可建改）
  </button>
  <button class="btn ghost" type="button" class:on={tab === 'outbound'} on:click={() => switchTab('outbound')}>
    外发清单
  </button>
</div>

{#if tab === 'pending'}
  <div class="panel" style="margin-bottom:1rem;">
    <div class="form-grid">
      <label
        >染程
        <select bind:value={form.dyeLotId}>
          {#each lots as lot}
            <option value={String(lot.id)}>{lot.recipeName} · {lot.fabricKg}kg</option>
          {/each}
        </select>
      </label>
      <label>检测时间 <input type="datetime-local" bind:value={form.checkedAt} /></label>
      <label>耐洗 (1–5) <input type="number" min="1" max="5" bind:value={form.washFastness} /></label>
      <label>摩擦 (&gt;0) <input type="number" step="0.1" min="0.1" bind:value={form.rubFastness} /></label>
      <label>温度 ℃ <input type="number" step="0.1" bind:value={form.tempC} /></label>
      <label>备注 <input bind:value={form.notes} /></label>
    </div>
    <div class="toolbar">
      <button class="btn" type="button" on:click={save}>{editing ? '保存修改' : '登记抽检'}</button>
      {#if editing}
        <button class="btn ghost" type="button" on:click={() => (editing = null)}>取消</button>
      {/if}
      {#if !isAdmin}
        <span class="hint">操作员可登记与修改未外发记录；外发需主管账号。</span>
      {/if}
    </div>
  </div>
{/if}

<div class="panel">
  {#if tab === 'outbound'}
    <div class="toolbar" style="margin-bottom:0.75rem;">
      <label style="display:flex;align-items:center;gap:0.5rem;">
        检测日期（UTC）
        <input type="date" bind:value={outboundDay} on:change={load} />
      </label>
      <button class="btn ghost small" type="button" on:click={load}>查询</button>
      <span class="hint">共 {rows.length} 条已外发，与总览「今日已外发」同源。</span>
    </div>
  {/if}
  {#if error}<p class="err">{error}</p>{/if}
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>染程</th>
        <th>检测时间</th>
        <th>耐洗</th>
        <th>摩擦</th>
        <th>温度</th>
        {#if tab === 'outbound'}<th>外发编号</th>{/if}
        <th>备注</th>
        {#if tab === 'pending'}<th></th>{/if}
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{lotLabel(row.dyeLotId)}</td>
          <td>{new Date(row.checkedAt).toLocaleString()}</td>
          <td>{row.washFastness}</td>
          <td>{row.rubFastness}</td>
          <td>{row.tempC}℃</td>
          {#if tab === 'outbound'}<td class="ref">{row.labRefNo}</td>{/if}
          <td>{row.notes || '—'}</td>
          {#if tab === 'pending'}
            <td class="row-actions">
              <button class="btn ghost small" type="button" on:click={() => startEdit(row)}>编辑</button>
              <button class="btn danger small" type="button" on:click={() => remove(row.id)}>删除</button>
              {#if isAdmin}
                <button class="btn small" type="button" on:click={() => dispatch(row)}>外发</button>
              {/if}
            </td>
          {/if}
        </tr>
      {:else}
        <tr><td colspan="8" style="text-align:center;color:var(--indigo-mist);padding:1.2rem;">
          {tab === 'outbound' ? '当日无已外发记录' : '暂无未外发抽检'}
        </td></tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .tabs {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  .tabs .on {
    outline: 1px solid var(--indigo-bright);
  }
  .hint {
    color: var(--indigo-mist);
    font-size: 0.8rem;
  }
  .ref {
    font-family: var(--font-display, monospace);
    letter-spacing: 0.03em;
  }
</style>
