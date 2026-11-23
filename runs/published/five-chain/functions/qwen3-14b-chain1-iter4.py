def score(board, placement):
    # Calculate holes
    holes = 0
    for col in range(10):
        has_filled_below = False
        for row in range(19, -1, -1):  # from bottom to top
            if board[row][col]:
                has_filled_below = True
            else:
                if has_filled_below:
                    holes += 1

    # Calculate column heights and surface roughness
    column_heights = []
    for col in range(10):
        height = 0
        for row in range(19, -1, -1):  # check from bottom up
            if board[row][col]:
                height += 1
            else:
                break
        column_heights.append(height)
    surface_roughness = sum(abs(column_heights[i] - column_heights[i + 1]) for i in range(9))
    max_height = max(column_heights)
    total_height = sum(column_heights)

    # Adjusted weights to prioritize minimizing holes and height
    lines_cleared = placement["lines_cleared"]
    base_score = (lines_cleared * 1000) - (holes * 500) - (surface_roughness * 250) - (max_height * 350) - (total_height * 25)

    # Ensure uniqueness by incorporating placement details
    kind_code = {'I': 0, 'O': 1, 'T': 2, 'S': 3, 'Z': 4, 'J': 5, 'L': 6}[placement['kind']]
    rotation_code = placement['rotation']
    column = placement['column']
    row = placement['row']
    unique_term = (kind_code + rotation_code + column + row) * 0.0001

    return base_score + unique_term
