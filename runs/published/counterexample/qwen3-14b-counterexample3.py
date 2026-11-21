def score(board, placement):
    # Calculate column heights
    heights = [0] * 10
    for col in range(10):
        count = 0
        for row in range(20):
            if board[row][col]:
                count += 1
        heights[col] = count

    # Calculate holes
    holes = 0
    for col in range(10):
        first_filled_row = None
        for row in range(20):
            if board[row][col]:
                first_filled_row = row
                break
        if first_filled_row is not None:
            for row in range(first_filled_row, 20):
                if not board[row][col]:
                    holes += 1

    # Calculate bumpiness
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])

    # Calculate max height
    max_height = max(heights)

    # Combine factors with weights
    lines_cleared = placement["lines_cleared"]
    return lines_cleared * 100 - holes * 10 - bumpiness * 5 - max_height * 2
