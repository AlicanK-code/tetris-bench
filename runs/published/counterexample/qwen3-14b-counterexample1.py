def score(board, placement):
    # Calculate column heights
    heights = [0] * 10
    for col in range(10):
        count = 0
        for row in range(20):
            if board[row][col]:
                count += 1
        heights[col] = count

    # Calculate max height
    max_height = max(heights)

    # Calculate number of holes
    holes = 0
    for col in range(10):
        min_filled_row = None
        for row in range(20):
            if board[row][col]:
                min_filled_row = row
                break
        if min_filled_row is not None:
            for row in range(min_filled_row, 20):
                if not board[row][col]:
                    holes += 1

    # Calculate bumpiness
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])

    # Combine factors with weights
    lines_cleared = placement["lines_cleared"]
    return lines_cleared * 1000 - holes * 100 - bumpiness * 50 - max_height * 20
