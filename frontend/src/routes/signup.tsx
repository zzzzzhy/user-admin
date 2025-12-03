import { Container, Flex, Image, Input, Text } from "@chakra-ui/react"
import {
  createFileRoute,
  redirect,
} from "@tanstack/react-router"
import { type SubmitHandler, useForm } from "react-hook-form"
import { useEffect, useState } from "react"
import { FiLock, FiUser } from "react-icons/fi"

import type { UserRegister } from "@/client"
import { Button } from "@/components/ui/button"
import { Field } from "@/components/ui/field"
import { InputGroup } from "@/components/ui/input-group"
import { PasswordInput } from "@/components/ui/password-input"
import {
  DialogRoot,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogTitle,
  DialogCloseTrigger,
} from "@/components/ui/dialog"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { confirmPasswordRules, emailPattern, passwordRules } from "@/utils"
import Logo from "/assets/images/dootask-logo.svg"

export const Route = createFileRoute("/signup")({
  component: SignUp,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
})

interface UserRegisterForm extends UserRegister {
  confirm_password: string
}

function SignUp() {
  const [showSuccessDialog, setShowSuccessDialog] = useState(false)
  const { signUpMutation, sendSmsCodeMutation } = useAuth({
    onSignUpSuccess: () => {
      setShowSuccessDialog(true)
    },
  })
  const [code, setCode] = useState("")
  const [countdown, setCountdown] = useState(0)
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
    watch,
  } = useForm<UserRegisterForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      full_name: "",
      phone: "",
      password: "",
      confirm_password: "",
    },
  })

  const phone = watch("phone")

  // Validate China phone number format
  function validatePhoneNumber(phoneNum: string): boolean | string {
    if (!phoneNum) {
      return "必须填写手机号"
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
      return "电话号码格式无效。必须是 11 位数字，从 1 开始，第二位数字为 3-9"
    }

    // Check for virtual numbers
    const virtualPrefixes = ["170", "171", "162", "165", "167", "166"]
    if (virtualPrefixes.includes(normalized.substring(0, 3))) {
      return "虚拟号码不被允许"
    }

    return true
  }

  // Countdown timer effect
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    if (countdown > 0) {
      interval = setInterval(() => {
        setCountdown((prev) => prev - 1)
      }, 1000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [countdown])

  const onSubmit: SubmitHandler<UserRegisterForm> = async (data) => {
    if (!code) {
      alert("Please enter the verification code")
      return
    }
    
    // Attach phone and SMS code to payload
    // @ts-ignore - augmenting form data with phone and sms_code
    data.sms_code = code
    await signUpMutation.mutateAsync(data)
  }

  async function sendCode(phoneNumber: string) {
    // Validate phone format before sending code
    const validationResult = validatePhoneNumber(phoneNumber)
    if (validationResult !== true) {
      return
    }
    
    try {
      await sendSmsCodeMutation.mutateAsync(phoneNumber)
      setCountdown(60)
    } catch {
      // error is handled by mutation onError
    }
  }

  return (
    
    <Flex flexDir={{ base: "column", md: "row" }} justify="center" h="100vh">
      <Container
        as="form"
        onSubmit={handleSubmit(onSubmit)}
        h="100vh"
        maxW="sm"
        alignItems="stretch"
        justifyContent="center"
        gap={4}
        centerContent
      >
        <Flex
          align="center"
          justify="center"
          gap={3}
          mb={6}
        >
          <Image
            src={Logo}
            alt="Dootask logo"
            height="60px"
            width="auto"
          />
          <Text
            fontSize="lg"
            fontWeight="bold"
            color="gray.700"
          >
            DooTask SaaS 体验版注册
          </Text>
        </Flex>
        <Field
          invalid={!!errors.full_name}
          errorText={errors.full_name?.message}
        >
          <InputGroup w="100%" startElement={<FiUser />}>
            <Input
              minLength={3}
              {...register("full_name", {
                required: "必须填写用户名",
              })}
              placeholder="用户名"
              type="text"
            />
          </InputGroup>
        </Field>

        <Field invalid={!!errors.email} errorText={errors.email?.message}>
          <InputGroup w="100%" startElement={<FiUser />}>
            <Input
              {...register("email", {
                required: "必须填写邮箱地址",
                pattern: emailPattern,
              })}
              placeholder="邮箱地址"
              type="email"
            />
          </InputGroup>
        </Field>
        <Field
          invalid={!!errors.phone}
          errorText={errors.phone?.message}
        >
          <InputGroup w="100%" startElement={<FiUser />}>
            <Input
              {...register("phone", {
                required: "必须填写手机号",
                validate: validatePhoneNumber,
              })}
              placeholder="手机号（仅限中国）"
              type="text"
            />
          </InputGroup>
        </Field>
        <Field invalid={false} errorText={""}>
          <Flex w="100%" gap={2}>
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="短信验证码"
              type="text"
            />
            <Button 
              variant="outline" 
              onClick={() => sendCode(phone)} 
              disabled={ phone.length !== 11 || countdown > 0}
              w="120px"
              flexShrink={0}
            >
              {countdown > 0 ? `倒计时: ${countdown}s` : "获取验证码"}
            </Button>
          </Flex>
        </Field>
        <PasswordInput
          type="password"
          startElement={<FiLock />}
          {...register("password", passwordRules())}
          placeholder="Password"
          errors={errors}
        />
        <PasswordInput
          type="confirm_password"
          startElement={<FiLock />}
          {...register("confirm_password", confirmPasswordRules(getValues))}
          placeholder="Confirm Password"
          errors={errors}
        />
        <Button variant="solid" type="submit" loading={isSubmitting} style={{ backgroundColor: "#8bcf70" }}>
          Sign Up
        </Button>
        {/* <Text>
          Already have an account?{" "}
          <RouterLink to="/login" className="main-link">
            Log In
          </RouterLink>
        </Text> */}
      </Container>

      <DialogRoot
        open={showSuccessDialog}
        onOpenChange={(details) => setShowSuccessDialog(details.open)}
      >
        <DialogContent>
          <DialogCloseTrigger />
          <DialogHeader>
            <DialogTitle>注册成功</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text>
              SaaS 登录相关信息已通过邮件发送到您的邮箱，请注意查收
            </Text>
          </DialogBody>
          <DialogFooter>
            <Button
              onClick={() => {
                setShowSuccessDialog(false)
                window.location.reload()
              }}
              style={{ backgroundColor: "#8bcf70" }}
            >
              确认
            </Button>
          </DialogFooter>
        </DialogContent>
      </DialogRoot>
    </Flex>
  )
}

export default SignUp
