import {
  Box,
  Button,
  Container,
  Flex,
  Heading,
  Input,
  Text,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"

import {
  type ApiError,
  type UserPublic,
  UsersService,
  type UserUpdateMe,
} from "@/client"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { emailPattern, handleError } from "@/utils"
import { Field } from "../ui/field"

const UserInformation = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const [editMode, setEditMode] = useState(false)
  const [phoneError, setPhoneError] = useState("")
  const { user: currentUser } = useAuth()
  const {
    register,
    handleSubmit,
    reset,
    getValues,
    formState: { isSubmitting, errors, isDirty },
  } = useForm<UserPublic>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      full_name: currentUser?.full_name,
      email: currentUser?.email,
      phone: currentUser?.phone,
    },
  })

  // Validate China phone number format
  function validatePhoneNumber(phoneNum: string | undefined): string {
    if (!phoneNum) {
      return ""
    }

    // Normalize phone number: remove spaces, +86, or 86 prefix
    let normalized = phoneNum.replace(/\s/g, "")
    if (normalized.startsWith("+86")) {
      normalized = normalized.substring(3)
    } else if (normalized.startsWith("86") && normalized.length > 11) {
      normalized = normalized.substring(2)
    }

    // Check format: 11 digits starting with 1, second digit 3-9
    const phoneRegex = /^1[3-9]\d{9}$/
    if (!phoneRegex.test(normalized)) {
      return "Invalid phone number format. Must be 11 digits starting with 1 and second digit 3-9"
    }

    // Check for virtual numbers
    const virtualPrefixes = ["170", "171", "162", "165", "167", "166"]
    if (virtualPrefixes.includes(normalized.substring(0, 3))) {
      return "Virtual numbers are not allowed"
    }

    return ""
  }

  const toggleEditMode = () => {
    setEditMode(!editMode)
  }

  const mutation = useMutation({
    mutationFn: (data: UserUpdateMe) =>
      UsersService.updateUserMe({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("User updated successfully.")
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries()
    },
  })

  const onSubmit: SubmitHandler<UserUpdateMe> = async (data) => {
    // Validate phone if provided
    if (data.phone) {
      const validationError = validatePhoneNumber(data.phone)
      if (validationError) {
        setPhoneError(validationError)
        return
      }
    }
    mutation.mutate(data)
  }

  const onCancel = () => {
    reset()
    setPhoneError("")
    toggleEditMode()
  }

  return (
    <Container maxW="full">
      <Heading size="sm" py={4}>
        User Information
      </Heading>
      <Box
        w={{ sm: "full", md: "sm" }}
        as="form"
        onSubmit={handleSubmit(onSubmit)}
      >
        <Field label="Full name">
          {editMode ? (
            <Input
              {...register("full_name", { maxLength: 30 })}
              type="text"
              size="md"
            />
          ) : (
            <Text
              fontSize="md"
              py={2}
              color={!currentUser?.full_name ? "gray" : "inherit"}
              truncate
              maxW="sm"
            >
              {currentUser?.full_name || "N/A"}
            </Text>
          )}
        </Field>
        <Field
          mt={4}
          label="Email"
          invalid={!!errors.email}
          errorText={errors.email?.message}
        >
          {editMode ? (
            <Input
              {...register("email", {
                required: "Email is required",
                pattern: emailPattern,
              })}
              type="email"
              size="md"
            />
          ) : (
            <Text fontSize="md" py={2} truncate maxW="sm">
              {currentUser?.email}
            </Text>
          )}
        </Field>
        <Field
          mt={4}
          label="Phone"
          invalid={!!phoneError}
          errorText={phoneError}
        >
          {editMode ? (
            <Input
              {...register("phone", { maxLength: 32 })}
              type="text"
              size="md"
              placeholder="Phone (China only)"
              onBlur={() => {
                const phone = getValues("phone")
                if (phone) {
                  const error = validatePhoneNumber(phone)
                  setPhoneError(error)
                } else {
                  setPhoneError("")
                }
              }}
              onChange={() => setPhoneError("")}
            />
          ) : (
            <Text
              fontSize="md"
              py={2}
              color={!currentUser?.phone ? "gray" : "inherit"}
              truncate
              maxW="sm"
            >
              {currentUser?.phone || "N/A"}
            </Text>
          )}
        </Field>
        <Flex mt={4} gap={3}>
          <Button
            variant="solid"
            onClick={toggleEditMode}
            type={editMode ? "button" : "submit"}
            loading={editMode ? isSubmitting : false}
            disabled={editMode ? !isDirty || !getValues("email") : false}
          >
            {editMode ? "Save" : "Edit"}
          </Button>
          {editMode && (
            <Button
              variant="subtle"
              colorPalette="gray"
              onClick={onCancel}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
          )}
        </Flex>
      </Box>
    </Container>
  )
}

export default UserInformation
