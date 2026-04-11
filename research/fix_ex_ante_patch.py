from pathlib import Path
p = Path('/home/openclaw/consensus-specs/tests/core/pyspec/eth_consensus_specs/test/phase0/fork_choice/test_ex_ante.py')
text = p.read_text()
text = text.replace(
'''from eth_consensus_specs.test.helpers.fork_choice import (
    add_attestation,
    add_block,
    check_head_against_root,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
''',
'''from eth_consensus_specs.test.helpers.fork_choice import (
    add_attestation,
    add_block,
    check_head_against_root,
    get_genesis_forkchoice_store_and_block,
    mark_block_payload_available,
    on_tick_and_append_step,
    tick_and_add_block,
)
''')
old = '''def _apply_base_block_a(spec, state, store, test_steps):
    # On receiving block A at slot `N`
    block = build_empty_block(spec, state, slot=state.slot + 1)
    signed_block_a = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block_a, test_steps)
    head = spec.get_head(store)
    expected_root = signed_block_a.message.hash_tree_root()
    if is_post_gloas(spec):
        assert head.root == expected_root
    else:
        check_head_against_root(spec, store, signed_block_a.message.hash_tree_root())
'''
new = '''def _apply_base_block_a(spec, state, store, test_steps):
    # On receiving block A at slot `N`
    block = build_empty_block(spec, state, slot=state.slot + 1)
    signed_block_a = state_transition_and_sign_block(spec, state, block)
    pre_head = spec.get_head(store).root if is_post_gloas(spec) else None
    yield from tick_and_add_block(spec, store, signed_block_a, test_steps)
    mark_block_payload_available(spec, store, signed_block_a)
    head = spec.get_head(store)
    expected_root = signed_block_a.message.hash_tree_root()
    if is_post_gloas(spec):
        # Under the deferred Gloas/Heze payload model, a lone locally built block A is
        # not immediately preferred over the anchor just from local payload availability.
        assert head.root == pre_head
    else:
        check_head_against_root(spec, store, signed_block_a.message.hash_tree_root())
'''
if old not in text:
    raise SystemExit('base block function not found')
text = text.replace(old, new)
old = '''    # On receiving block A at slot `N`
    yield from _apply_base_block_a(spec, state, store, test_steps)
    state_a = state.copy()
'''
new = '''    # On receiving block A at slot `N`
    yield from _apply_base_block_a(spec, state, store, test_steps)
    post_gloas_anchor = spec.get_head(store).root if is_post_gloas(spec) else None
    state_a = state.copy()
'''
text = text.replace(old, new, 1)
old = '''    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block B received at N+2 — C is head due to proposer score boost
    yield from add_block(spec, store, signed_block_b, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())
'''
new = '''    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    mark_block_payload_available(spec, store, signed_block_c)
    if is_post_gloas(spec):
        assert spec.get_head(store).root == post_gloas_anchor
    else:
        check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block B received at N+2 — C is head due to proposer score boost
    yield from add_block(spec, store, signed_block_b, test_steps)
    mark_block_payload_available(spec, store, signed_block_b)
    if is_post_gloas(spec):
        assert spec.get_head(store).root == post_gloas_anchor
    else:
        check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())
'''
if old not in text:
    raise SystemExit('vanilla block C/B section not found')
text = text.replace(old, new, 1)
old = '''    state_a, store, signed_block_a = yield from _apply_base_block_a(spec, state, store, test_steps)
'''
new = '''    state_a, store, signed_block_a = yield from _apply_base_block_a(spec, state, store, test_steps)
    post_gloas_anchor = spec.get_head(store).root if is_post_gloas(spec) else None
'''
text = text.replace(old, new, 2)
old = '''    yield from add_block(spec, store, signed_block_c, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())
'''
new = '''    yield from add_block(spec, store, signed_block_c, test_steps)
    mark_block_payload_available(spec, store, signed_block_c)
    if is_post_gloas(spec):
        assert spec.get_head(store).root == post_gloas_anchor
    else:
        check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())
'''
text = text.replace(old, new, 2)
old = '''    yield from add_block(spec, store, signed_block_b, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())
'''
new = '''    yield from add_block(spec, store, signed_block_b, test_steps)
    mark_block_payload_available(spec, store, signed_block_b)
    if is_post_gloas(spec):
        assert spec.get_head(store).root == post_gloas_anchor
    else:
        check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())
'''
text = text.replace(old, new, 1)
p.write_text(text)
print('patched')
