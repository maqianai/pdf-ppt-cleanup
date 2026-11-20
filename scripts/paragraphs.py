"""Conservative geometric grouping into editable rich-text paragraphs."""
import statistics


def paragraphs(lines):
    groups = []
    for line in sorted(lines, key=lambda x: (x['bbox'][1], x['bbox'][0])):
        best = None
        for group in reversed(groups):
            prev = group[-1]
            size = max(s['size'] for s in line['runs'])
            old_size = max(s['size'] for s in prev['runs'])
            delta = line['baseline'] - prev['baseline']
            if not (0.65 * min(size, old_size) < delta <= 1.85 * max(size, old_size)):
                continue
            if max(size, old_size) / min(size, old_size) > 1.3:
                continue
            left = abs(line['bbox'][0] - prev['bbox'][0])
            center = abs((line['bbox'][0] + line['bbox'][2] - prev['bbox'][0] - prev['bbox'][2]) / 2)
            # Separate columns and styles; a centered last line may be shorter.
            overlap = min(line['bbox'][2], prev['bbox'][2]) - max(line['bbox'][0], prev['bbox'][0])
            if min(left, center) > 3 or overlap <= 0:
                continue
            new_fonts = {s['original_font'] for s in line['runs']}
            old_fonts = {s['original_font'] for s in prev['runs']}
            if not new_fonts.intersection(old_fonts):
                continue
            best = group
            break
        if best is None:
            groups.append([line])
        else:
            best.append(line)
    result = []
    for group in groups:
        box = [min(x['bbox'][0] for x in group), min(x['bbox'][1] for x in group),
               max(x['bbox'][2] for x in group), max(x['bbox'][3] for x in group)]
        centers = [(x['bbox'][0] + x['bbox'][2]) / 2 for x in group]
        lefts = [x['bbox'][0] for x in group]
        align = 'center' if len(group) > 1 and max(centers) - min(centers) <= 3 and max(lefts) - min(lefts) > 3 else 'left'
        # Equal-width centered lines look identical with left alignment. Detect a
        # centered short final line above, without forcing all text to center.
        runs = []
        for i, line in enumerate(group):
            for j, span in enumerate(line['runs']):
                runs.append({**span, 'soft_break_before': i > 0 and j == 0})
        first = group[0]['runs'][0]
        gaps = [b['baseline'] - a['baseline'] for a, b in zip(group, group[1:])]
        result.append({**first, 'text': '\n'.join(x['text'] for x in group),
                       'bbox': box, 'baseline': group[0]['baseline'],
                       'size': max(x['size'] for x in group[0]['runs']),
                       'runs': runs, 'align': align, 'source_lines': len(group),
                       'line_spacing': statistics.median(gaps) if gaps else None})
    return result
