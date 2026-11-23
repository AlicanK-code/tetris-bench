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

    # Calculate number of holes
    num_holes = 0
    for col in range(10):
        has_filled = False
        for row in range(20):
            if board[row][col]:
                has_filled = True
            elif has_filled:
                num_holes += 1

    # Calculate surface roughness (bumpiness)
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
    bumpiness = 0
    for i in range(1, 10):
        bumpiness += (surface_heights[i] - surface_heights[i-1])**2

    # Calculate sum of squares of column heights
    sum_squares = sum(h**2 for h in column_heights)

    # Combine factors into a score
    lines = placement["lines_cleared"]
    return float(lines * 1000 - max_height * 50 - num_holes * 10 - bumpiness * 5 - sum_squares * 5)
