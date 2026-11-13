extends SceneTree

# Loaded by `assetforge engine-check`: instantiate the imported scene and count
# its nodes by class. One AF_RESULT line carries the answer; the exit code
# says whether Godot could load what it imported.

func _count(node: Node, totals: Dictionary) -> void:
	var kind := node.get_class()
	totals[kind] = int(totals.get(kind, 0)) + 1
	for child in node.get_children():
		_count(child, totals)

func _init() -> void:
	var packed = load("res://asset.glb")
	if packed == null:
		print("AF_RESULT " + JSON.stringify({"ok": false, "error": "Godot could not load the imported scene"}))
		quit(1)
		return
	var root = packed.instantiate()
	if root == null:
		print("AF_RESULT " + JSON.stringify({"ok": false, "error": "the imported scene could not be instantiated"}))
		quit(1)
		return
	var totals := {}
	_count(root, totals)
	var animations := []
	for player in root.find_children("*", "AnimationPlayer", true, false):
		for name in player.get_animation_list():
			animations.append(String(name))
	print("AF_RESULT " + JSON.stringify({"ok": true, "nodes": totals, "animations": animations}))
	root.free()
	quit(0)
