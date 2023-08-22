from tree_sitter import Parser

class Capture:
    def __init__(self, nodes, output, list_forms=None):
        self.nodes = nodes
        self.output = output
        self.list_forms = list_forms or {}
    def format(self, strings):
        dct = {}
        for name, node in self.nodes.items():
            if name == 'root':
                continue
            if isinstance(node, list):
                strs = [strings[n.id] for n in node]
                j = ' '
                if name in self.list_forms:
                    j = self.list_forms[name].get('join', ' ')
                dct[name] = j.join(strs)
                # TODO: more complex lists
            else:
                dct[name] = strings[node.id]
        return self.output.format(**dct)
    def requirements(self):
        for name, node in self.nodes.items():
            if isinstance(node, list):
                for n in node:
                    yield name, n
            else:
                yield name, node
    def make_null(node):
        dct = {'root': node}
        ls = [node.type.replace('{', '{{').replace('}', '}}')]
        for i, ch in enumerate(node.children):
            n = 'ch%s' % i
            ls.append('{'+n+'}')
            dct[n] = ch
        pat = '(' + ' '.join(ls) + ')'
        return Capture(dct, pat)

class Pattern:
    def __init__(self, language, query_string, output):
        self.query = language.query(query_string)
        self.output = output
    def satisfies(self, cond, dct):
        for c in cond:
            if 'has' in c and c['has'] not in dct:
                return False
            if 'len' in c:
                name = c['len']
                lmin = c.get('min', -1)
                lmax = c.get('max', -1)
                leq = c.get('equal', -1)
                ls = dct.get(c, None)
                if not ls and leq != 0:
                    return False
                if not isinstance(ls, list):
                    return False
                if leq != -1 and leq != len(ls):
                    return False
                if lmin > len(ls):
                    return False
                if len(ls) > lmax > -1:
                    return False
        return True
    def make_capture(self, dct):
        root_name = 'root'
        for name in ['root', 'root_text']:
            if name in dct:
                root_name = name
                break
        else:
            raise ValueError('Pattern did not capture @root')
        if isinstance(self.output, str):
            return Capture(dct, self.output)
        for option in self.output:
            if not self.satisfies(option.get('cond', []), dct):
                continue
            return Capture(dct, option.get('output', ''),
                           list_forms=option.get('lists', {}))
        return Capture.make_null(dct[root_name])
    def match(self, tree):
        cur = {}
        seen_roots = set()
        for node, name in self.query.captures(tree):
            loc = (node.start_point, node.end_point)
            if name in ['root', 'root_text'] and loc not in seen_roots:
                if cur:
                    yield self.make_capture(cur)
                seen_roots.add(loc)
                cur = {}
            if name.endswith('_list'):
                if name not in cur:
                    cur[name] = []
                cur[name].append(node)
            else:
                cur[name] = node
        if cur:
            yield self.make_capture(cur)
    def from_json(language, obj):
        return Pattern(language, obj['pattern'], obj['output'])

class PatternApplier:
    def __init__(self, queries, tree, bytestring):
        self.queries = queries
        self.bytestring = bytestring
        self.tree = tree
        self.matches = {}
    def apply_patterns(self):
        for qr in self.queries:
            for cap in qr.match(self.tree):
                root = cap.nodes.get('root', cap.nodes.get('root_text'))
                if not root:
                    # TODO: should probably issue a warning or an error
                    continue
                self.matches.setdefault(root.id, cap)
    def get_str(self, node):
        return self.bytestring[node.start_byte:node.end_byte].decode('utf-8')
    def translate(self):
        todo = [self.tree]
        done = {}
        while todo:
            cur = todo[-1]
            if cur.id in done:
                todo.pop()
                continue
            elif cur.id not in self.matches:
                self.matches[cur.id] = Capture.make_null(cur)
            cap = self.matches[cur.id]
            incomplete = []
            for name, node in cap.requirements():
                if name != 'root' and node.id not in done:
                    if name.endswith('_text'):
                        done[node.id] = self.get_str(node)
                    else:
                        incomplete.append(node)
            if incomplete:
                todo += incomplete
            else:
                todo.pop()
                done[cur.id] = cap.format(done)
        return done[self.tree.id]

def maybe_read_file(obj):
    if hasattr(obj, 'read'):
        return obj.read()
    else:
        return obj

def to_str(obj):
    o2 = maybe_read_file(obj)
    if isinstance(o2, bytes):
        return o2.decode('utf-8')
    return o2

def to_bytes(obj):
    o2 = maybe_read_file(obj)
    if isinstance(obj, str):
        return o2.encode('utf-8')
    return o2

def load_patterns(json_list, language):
    return [Pattern.from_json(language, obj) for obj in json_list]

def translate(patterns, language, input_text):
    p = Parser()
    p.set_language(language)
    byt = to_bytes(input_text)
    tree = p.parse(byt).root_node
    app = PatternApplier(patterns, tree, byt)
    app.apply_patterns()
    return app.translate()
