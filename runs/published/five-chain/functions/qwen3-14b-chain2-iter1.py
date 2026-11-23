def score(board, placement):
    # Calculate column heights and max height
    column_heights = []
    max_height = 0
    for col in range(10):
        current_h = 0
        for row in range(19, -1, -1):
            if board[row][col]:
                current_h += 1
            else:
                break
        column_heights.append(current_h)
        if current_h > max_height:
            max_height = current_h

    # Calculate number of holes correctly
    num_holes = 0
    for col in range(10):
        has_filled = False
        for row in range(20):
            if board[row][col]:
                has_filled = True
            elif has_filled:
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
    return float(lines * 200 - max_height * 20 - num_holes * 10 - roughness * 5 - sum(column_heights) * 2)
