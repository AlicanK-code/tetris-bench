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

    # Calculate column heights
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

    # Adjusted weights for better performance
    lines_cleared = placement["lines_cleared"]
    base_score = (lines_cleared * 1000) - (holes * 250) - (surface_roughness * 120) - (max_height * 200) - (total_height * 10)

    # Add a small term based on placement to ensure uniqueness
    kind_code = {'I': 0, 'O': 1, 'T': 2, 'S': 3, 'Z': 4, 'J': 5, 'L': 6}[placement['kind']]
    rotation_code = placement['rotation']
    unique_term = (kind_code + rotation_code) * 0.0001

    return base_score + unique_term
