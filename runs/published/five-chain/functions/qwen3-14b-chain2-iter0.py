def score(board, placement):
    # Calculate maximum column height
    max_height = 0
    for col in range(10):
        current_h = 0
        for row in range(19, -1, -1):
            if board[row][col]:
                current_h += 1
            else:
                break
        if current_h > max_height:
            max_height = current_h

    # Calculate number of holes
    num_holes = 0
    for col in range(10):
        hfr = None
        for row in range(20):
            if board[row][col]:
                hfr = row
                break
        if hfr is None:
            continue
        for row in range(hfr + 1, 20):
            if not board[row][col]:
                num_holes += 1

    # Calculate surface roughness
    surface_heights = []
    for col in range(10):
        hfr = None
        for row in range(20):
            if board[row][col]:
                hfr = row
                break
        if hfr is None:
            surface_heights.append(20)
        else:
            surface_heights.append(hfr)
    roughness = 0
    for i in range(1, 10):
        roughness += abs(surface_heights[i] - surface_heights[i - 1])

    # Combine factors into a score
    lines = placement["lines_cleared"]
    return float(lines * 100 - max_height * 10 - num_holes * 5 - roughness * 2)
