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

    # Calculate number of holes correctly
    holes = 0
    for col in range(10):
        for row in range(20):
            if not board[row][col]:
                # Check if there's any filled cell below
                has_filled_below = False
                for r in range(row + 1, 20):
                    if board[r][col]:
                        has_filled_below = True
                        break
                if has_filled_below:
                    holes += 1

    # Calculate bumpiness
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])

    # Combine factors with weights
    lines_cleared = placement["lines_cleared"]
    return lines_cleared * 1000 - max_height * 100 - holes * 50 - bumpiness * 20
