<script>
  import { onMount } from 'svelte';
  import { api, toLocalInput, fromLocalInput } from '../lib/api.js';
  import { user } from '../lib/auth.js';

  let lots = [];
  let rows = [];
  let error = '';
  let view = 'pending'; // pending=未外发（默认）；dispatched=外发清单
  let day = ''; // 外发清单按检测日过滤 YYYY-MM-DD
  let form = {
    dyeLotId: '',
    checkedAt: toLocalInput(new Date().toISOString()),
    washFastness: 4,
    rubFastness: 3.5,
    tempC: 40,
    notes: '',
  };
  let editing = null;

  $: isAdmin = $user?.role === 'admin';

  async function load() {
    error = '';
    try {
      const query =
        view === 'dispatched'
          ? `/fastness-checks?dispatched=true${day ? `&day=${day}` : ''}`
          : '/fastness-checks';
      const lotReq = lots.length ? Promise.resolve(lots) : api('/dye-lots');
      [lots, rows] = await Promise.all([lotReq, api(query)]);
      if (!form.dyeLotId && lots.length) form.dyeLotId = String(lots[0].id);
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  function switchView(next) {
    view = next;
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

  async function dispatch(row) {
    const input = prompt(
      `输入实验室外发编号（同坊唯一）；留空则由系统生成。\n染程：${lotLabel(row.dyeLotId)}`,
      ''
    );
    if (input === null) return;
    error = '';
    try {
      const body = input.trim() ? JSON.stringify({ outboundNo: input.trim() }) : '{}';
      await api(`/fastness-checks/${row.id}/dispatch`, { method: 'POST', body });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">色牢度抽检</h1>
<p class="page-sub">
  耐洗 1–5 级；摩擦牢度须大于 0；记录检测温度。抽检一旦外发（取得实验室外发编号），
  耐洗、耐摩擦、温度即<strong>锁定不可改</strong>；默认列表仅显示未外发，已外发记录见「外发清单」。
</p>

<div class="toolbar" style="margin-bottom:1rem;">
  <button
    class="btn"
    type="button"
    class:ghost={view !== 'pending'}
    on:click={() => switchView('pending')}
  >
    未外发
  </button>
  <button
    class="btn"
    type="button"
    class:ghost={view !== 'dispatched'}
    on:click={() => switchView('dispatched')}
  >
    外发清单
  </button>
  {#if view === 'dispatched'}
    <label class="day-filter">
      按检测日
      <input type="date" bind:value={day} on:change={load} />
    </label>
    <button class="btn ghost small" type="button" on:click={() => { day = ''; load(); }}>全部</button>
    <span class="row-count">共 {rows.length} 条</span>
  {/if}
</div>

{#if view === 'pending'}
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
      <span class="hint">新建外发编号为空；操作员可登记与修改，外发动作仅主管可执行。</span>
    </div>
    {#if error}<p class="err">{error}</p>{/if}
  </div>

  <div class="panel">
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>染程</th>
          <th>检测时间</th>
          <th>耐洗</th>
          <th>摩擦</th>
          <th>温度</th>
          <th>备注</th>
          <th></th>
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
            <td>{row.notes || '—'}</td>
            <td class="row-actions">
              <button class="btn ghost small" type="button" on:click={() => startEdit(row)}>编辑</button>
              {#if isAdmin}
                <button class="btn small" type="button" on:click={() => dispatch(row)}>外发</button>
              {/if}
              <button class="btn danger small" type="button" on:click={() => remove(row.id)}>删除</button>
            </td>
          </tr>
        {:else}
          <tr><td colspan="8" class="empty">暂无未外发抽检</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
{:else}
  <div class="panel">
    {#if error}<p class="err">{error}</p>{/if}
    <table>
      <thead>
        <tr>
          <th>外发编号</th>
          <th>ID</th>
          <th>染程</th>
          <th>检测时间</th>
          <th>耐洗</th>
          <th>摩擦</th>
          <th>温度</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row}
          <tr>
            <td class="locked-no">{row.outboundNo}</td>
            <td>{row.id}</td>
            <td>{lotLabel(row.dyeLotId)}</td>
            <td>{new Date(row.checkedAt).toLocaleString()}</td>
            <td>{row.washFastness}</td>
            <td>{row.rubFastness}</td>
            <td>{row.tempC}℃</td>
            <td>{row.notes || '—'}</td>
          </tr>
        {:else}
          <tr><td colspan="8" class="empty">该条件下暂无已外发抽检</td></tr>
        {/each}
      </tbody>
    </table>
    <p class="hint" style="margin:0.75rem 0 0;">
      外发记录测值已锁定，仅供查阅；看板「近 24 时已外发」与本清单同为已外发口径。
    </p>
  </div>
{/if}

<style>
  .day-filter {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.85rem;
    color: var(--indigo-mist);
  }

  .row-count {
    margin-left: auto;
    font-size: 0.85rem;
    color: var(--indigo-mist);
  }

  .hint {
    color: var(--indigo-mist);
    font-size: 0.8rem;
  }

  .locked-no {
    font-family: var(--font-display);
    letter-spacing: 0.03em;
    color: var(--ok, #4caf82);
    white-space: nowrap;
  }

  .empty {
    text-align: center;
    color: var(--indigo-mist);
    padding: 1.25rem 0;
  }
</style>
